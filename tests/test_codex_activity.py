import copy
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time

import pytest

from repomind.codex_activity import ActivityLog, safe_text
from repomind.codex_process import stream_process
from repomind.web.tasks import TaskService
from test_task_workbench import project, wait


def command(i, code, text='python -m pytest tests/test_api.py', output=''):
    return {'type': 'item.started' if code is None else 'item.completed', 'item': {
        'id': str(i), 'type': 'command_execution', 'command': text,
        'exit_code': code, 'status': 'in_progress' if code is None else 'completed', 'aggregated_output': output}}


def test_failure_is_immutable_and_retry_is_derived_without_merging_redacted_commands():
    log = ActivityLog();log.observe(command(1, 1, output='assertion failed'))
    original = copy.deepcopy(log.data['events'])
    log.observe(command(2, 0, text='python -m pytest tests/other.py'))
    assert log.view()['failures'][0]['retry_outcome'] == 'unknown'
    log.observe(command(3, None));assert log.view()['failures'][0]['retry_outcome'] == 'running'
    log.observe(command(3, 0));assert log.view()['failures'][0]['retry_outcome'] == 'succeeded'
    assert log.data['events'][:1] == original
    assert log.view()['failures'][0]['reason'] == 'assertion failed'


def test_parallel_command_already_started_is_not_a_retry():
    log=ActivityLog();log.observe(command(1,None));log.observe(command(2,None))
    log.observe(command(1,1,output='failure'));log.observe(command(2,0))
    assert log.view()['failures'][0]['retry_outcome']=='unknown'


def test_denied_command_without_an_exit_code_retains_reason():
    event=command(1,None,output='permission denied');event['type']='item.completed';event['item']['status']='failed'
    log=ActivityLog();log.observe(event)
    failure,=log.view()['failures']
    assert failure['exit_code'] is None and failure['reason']=='permission denied'


@pytest.mark.parametrize('body', [
    '--password=hunter2', 'TOKEN=private_value', '{"api_key": "private_value"}',
    '--secret "private value"', 'https://x.test/?access_token=private_value&safe=1',
    'https://name:hunter2@x.test', 'Authorization: Bearer abcdefghijklmnop',
    'Cookie: session=private_value; auth=hunter2', 'Authorization: Bearer hunter2',
])
def test_commands_and_outputs_redact_credentials(body):
    result = safe_text(body)
    assert 'hunter2' not in result and 'private_value' not in result and 'private value' not in result
    assert 'abcdefghijklmnop' not in result and '[REDACTED]' in result


def test_known_secret_is_removed_before_truncation_and_reasoning_is_not_saved(monkeypatch):
    monkeypatch.setenv('REPOMIND_API_KEY', 'a-secret-without-standard-prefix')
    log = ActivityLog();log.observe(command(1, 1, 'echo a-secret-without-standard-prefix', 'a-secret-without-standard-prefix'))
    log.observe({'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'PRIVATE REASONING'}})
    saved = json.dumps(log.data)
    assert 'a-secret-without-standard-prefix' not in saved and 'PRIVATE REASONING' not in saved
    assert len(safe_text('x' * 20000)) < 8100


def test_stream_emits_events_before_exit_and_drains_stderr():
    seen=[];ready=threading.Event();finished=threading.Event();results=[]
    code='import sys,time;print('+repr(json.dumps(command(1,1,output='failure')))+',flush=True);sys.stderr.write("x"*100000);sys.stderr.flush();time.sleep(.6)'
    def run():
        results.append(stream_process([sys.executable,'-u','-c',code],input='',encoding='utf-8',cancel=threading.Event(),timeout=5,
                                      on_event=lambda e:(seen.append(e),ready.set())))
        finished.set()
    t=threading.Thread(target=run);t.start()
    assert ready.wait(3) and not finished.is_set()
    t.join(8);assert not t.is_alive() and results[0].returncode==0
    assert len(results[0].stderr)==100000 and seen[0]['item']['exit_code']==1


def test_nonzero_cli_process_has_its_own_sanitized_failure_record():
    log=ActivityLog()
    result=stream_process([sys.executable,'-c','import sys;sys.stderr.write("TOKEN=private_value network failed");sys.exit(7)'],
                          input='',encoding='utf-8',cancel=threading.Event(),on_event=log.observe)
    assert result.returncode==7
    failure,=log.view()['failures']
    assert failure['exit_code']==7 and 'network failed' in failure['reason']
    assert 'private_value' not in json.dumps(log.data)


@pytest.mark.parametrize('kind',['timeout','cancel','limit','callback'])
def test_stream_terminates_on_timeout_cancel_limits_or_observer_error(kind,monkeypatch):
    cancelled=threading.Event()
    if kind=='limit':monkeypatch.setattr('repomind.codex_process.MAX_LINE',1000)
    code='import time;print("x"*2000,flush=True);time.sleep(30)' if kind=='limit' else 'import time;print("{}",flush=True);time.sleep(30)'
    if kind=='cancel':cancelled.set()
    def callback(_):
        if kind=='callback':raise ValueError('observer failed')
    start=time.monotonic()
    with pytest.raises(ValueError):
        stream_process([sys.executable,'-u','-c',code],input='',encoding='utf-8',cancel=cancelled,timeout=.3,on_event=callback)
    assert time.monotonic()-start < 8


def test_activity_is_durable_during_running_failure_and_restart(project,monkeypatch):
    root,db=project;release=threading.Event();observed=threading.Event()
    monkeypatch.setattr(TaskService,'environment',lambda *_:{'ready':True,'checks':[]})
    def fake(*args,runner,**kwargs):
        text='import sys;print('+repr(json.dumps(command(1,1,'python broken.py --token fixture-secret','TOKEN=fixture-secret failure')))+',flush=True)'
        runner([sys.executable,'-u','-c',text],input='',encoding='utf-8',timeout=5)
        observed.set();release.wait(5);raise ValueError('failed --password private_value')
    service=TaskService(db,{'RepoMind':root},run=fake)
    try:
        task=service.prepare('RepoMind','Verify failure feedback');tid=task['task_id'];service.start('RepoMind',tid)
        assert observed.wait(5)
        row=service.get('RepoMind',tid)
        assert row['status']=='running' and row['elapsed_seconds']>=0
        assert row['activity']['failures'][0]['exit_code']==1
        with sqlite3.connect(db) as c:
            saved=c.execute('select activity from web_task_activity').fetchone()[0]
            assert 'fixture-secret' not in saved and '[REDACTED]' in saved
        release.set();row=wait(service,tid)
        assert row['status']=='failed' and 'private_value' not in row['error']
        elapsed=row['elapsed_seconds'];time.sleep(.03);assert service.get('RepoMind',tid)['elapsed_seconds']==elapsed
        with sqlite3.connect(db) as c:
            original=json.loads(c.execute('select receipt from web_tasks').fetchone()[0]);original['status']='running'
            c.execute('update web_tasks set status=?,receipt=?',('running',json.dumps(original)))
    finally:release.set();service.close()
    again=TaskService(db,{'RepoMind':root})
    try:
        row=again.get('RepoMind',tid)
        assert row['status']=='interrupted' and row['activity']['failures'][0]['exit_code']==1
        with pytest.raises(ValueError):again.get('Other',tid)
    finally:again.close()


def test_old_receipt_remains_unchanged_and_missing_details_stay_unknown(project):
    root,db=project
    with TaskServiceContext(db,root) as service:
        row={'task_id':'task-old','project':'RepoMind','status':'completed','result':{'tool_errors':[{'exit_code':1}]},
             'started_at':'2026-11-09T00:00:00+00:00','ended_at':'2026-11-09T00:01:00+00:00'}
        with sqlite3.connect(db) as c:c.execute('insert into web_tasks values(?,?,?,?)',('task-old','RepoMind','completed',json.dumps(row)))
        data=service.get('RepoMind','task-old')
        assert data['elapsed_seconds']==60 and data['activity']['source']=='legacy'
        assert data['activity']['failures'][0]['retry_outcome']=='unknown'
        with sqlite3.connect(db) as c:assert json.loads(c.execute('select receipt from web_tasks').fetchone()[0])==row


class TaskServiceContext:
    def __init__(self,db,root):self.service=TaskService(db,{'RepoMind':root})
    def __enter__(self):return self.service
    def __exit__(self,*args):self.service.close()
