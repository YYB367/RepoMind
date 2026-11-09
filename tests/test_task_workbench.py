import json
import os
from pathlib import Path
import subprocess
import time

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.codex_flow import capture, recall
from repomind.memory.review import ReviewQueue, read_record
from repomind.web.evidence import MAX_FILE, changes, git, preview, snapshot
from repomind.web.tasks import TaskService


@pytest.fixture
def project(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    (root/'decision.py').write_text("mode = 'old'\n",encoding='utf-8')
    for args in (['init','-q'],['add','.'],['-c','user.name=Tests','-c','user.email=test@invalid.local','commit','-qm','initial']):
        subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True)
    return root,tmp_path/'ledger.sqlite3'


def candidate(root,db,*,path=None,commit=None):
    quote="mode = 'old'"
    artifact=read_record(path or root/'decision.py',commit=commit,repo=root,
                         recorded_at=None if commit else '2020-01-01T00:00:00Z',quote=quote)
    with SQLiteMemoryStore(db) as store:
        row,_=ReviewQueue(store).propose(artifact=artifact,quote=quote,project_id='RepoMind',subject='app',
            predicate='mode',value='old',event_type='declare',effective_at=None)
    return row


def wait(service,tid):
    for _ in range(150):
        row=service.get('RepoMind',tid)
        if row['status'] not in {'queued','running'}:return row
        time.sleep(.02)
    raise AssertionError('task did not end')


def test_real_file_changes_capture_review_and_later_recall_share_database(project,monkeypatch):
    root,db=project
    def fake(root,database,project,prompt,**kwargs):
        assert kwargs['workspace_write'] and 'mode' not in prompt
        (root/'decision.py').write_text("mode = 'reference'\n",encoding='utf-8')
        message='Done.\n```repomind-memory\n'+json.dumps([{'path':'decision.py','quote':"mode = 'reference'",
            'subject':'app','field':'mode','value':'reference','event_type':'complete','reason':'The implemented file records the project default.'}])+ '\n```'
        return {'session_id':'fake-session','assistant_message':'Implemented.','capture':capture(root,database,project,message)}
    monkeypatch.setattr(TaskService,'environment',lambda *_:{'ready':True,'checks':[]})
    service=TaskService(db,{'RepoMind':root},run=fake)
    try:
        prepared=service.prepare('RepoMind','Improve the implementation and verify it.')
        service.start('RepoMind',prepared['task_id']);done=wait(service,prepared['task_id'])
        assert done['status']=='completed' and '_before' not in done
        assert len(done['changes'])==1 and "+mode = 'reference'" in done['changes'][0]['diff']
        row=done['candidates'][0];assert row['status']=='pending' and row['rationale']
        assert recall(db,'RepoMind','app mode')==[]
        with SQLiteMemoryStore(db) as store:
            c=ReviewQueue(store).show('RepoMind',row['candidate_id'])
            stored=store.connection.execute('SELECT candidate_json FROM memory_review_candidates WHERE candidate_id=?',(c.candidate_id,)).fetchone()[0]
            assert 'rationale' not in json.loads(stored)
            assert store.connection.execute('SELECT rationale FROM memory_review_notes WHERE candidate_id=?',(c.candidate_id,)).fetchone()[0]
            p=service.candidate_preview('RepoMind',c)
            assert p['scope']=='task_snapshot' and p['version_match']
            (root/'decision.py').write_text('changed again',encoding='utf-8')
            p=service.candidate_preview('RepoMind',c)
            assert p['changed'] and "reference" in p['text'] and p['version_match']
            ReviewQueue(store).decide('RepoMind',c.candidate_id,1,decision='confirmed')
        assert service.get('RepoMind',prepared['task_id'])['candidates'][0]['status']=='confirmed'
        assert recall(db,'RepoMind','app mode')[0]['value']=='reference'
        with pytest.raises(ValueError):service.get('Other',prepared['task_id'])
    finally:service.close()


def test_git_preview_reads_exact_committed_version(project):
    root,db=project
    commit=git(root,'rev-parse','HEAD').decode().strip()
    row=candidate(root,db,path=Path('decision.py'),commit=commit)
    (root/'decision.py').write_text('new contents',encoding='utf-8')
    p=preview(root,row)
    assert p['scope']=='git' and p['changed'] and p['version_match']
    assert p['text']=="mode = 'old'\n"


@pytest.mark.parametrize('failure',['changed','missing','large','binary','link'])
def test_failed_file_preview_falls_back_to_quote_without_altering_candidate(project,failure,tmp_path):
    root,db=project;row=candidate(root,db);path=root/'decision.py'
    if failure=='missing':path.unlink()
    elif failure=='large':path.write_bytes(b'x'*(MAX_FILE+1))
    elif failure=='binary':path.write_bytes(b'\x00binary')
    elif failure=='link':
        outside=tmp_path/'outside.py';outside.write_text('PRIVATE')
        path.unlink()
        os.link(outside,path)
    else:path.write_text('newer')
    p=preview(root,row)
    assert p['scope']=='quote' and not p['version_match'] and p['warning']
    assert p['text']==row.quote and row.status=='pending'


def test_outside_project_and_sensitive_paths_are_never_read(project,tmp_path):
    root,db=project;outside=tmp_path/'outside.py';outside.write_text("mode = 'old'\n")
    row=candidate(root,db,path=outside)
    assert preview(root,row)['scope']=='quote'
    assert preview(None,row)['scope']=='quote'
    (root/'.env').write_text('private')
    (root/'credentials.txt').write_text('private')
    assert not {'.env','credentials.txt'} & snapshot(root).keys()


def test_snapshot_handles_large_file_transition_and_does_not_include_existing_diff(project):
    root,_=project
    (root/'decision.py').write_text('preexisting user edits\n')
    before=snapshot(root)
    assert changes(before,snapshot(root))==[]
    (root/'decision.py').write_bytes(b'x'*(MAX_FILE+1))
    changed,=changes(before,snapshot(root))
    assert changed['kind']=='modified' and changed['diff'] is None and changed['after']['unavailable']


def test_service_lease_restart_and_preflight_gate(project,monkeypatch):
    root,db=project
    monkeypatch.setattr(TaskService,'environment',lambda *_:{'ready':False,'checks':[]})
    service=TaskService(db,{'RepoMind':root})
    try:
        with pytest.raises(ValueError,match='已有任务服务'):TaskService(db,{'RepoMind':root})
        task=service.prepare('RepoMind','Do work')
        with pytest.raises(ValueError,match='预查'):service.start('RepoMind',task['task_id'])
        with SQLiteMemoryStore(db) as store:
            task['status']='running';service._save(store,task)
    finally:service.close()
    again=TaskService(db,{'RepoMind':root})
    try:assert again.get('RepoMind',task['task_id'])['status']=='interrupted'
    finally:again.close()


def test_failure_retains_file_changes_and_never_creates_formal_memory(project,monkeypatch):
    root,db=project
    monkeypatch.setattr(TaskService,'environment',lambda *_:{'ready':True,'checks':[]})
    def fake(*args,**kwargs):
        (root/'decision.py').write_text('partial change')
        raise ValueError('sandbox failed')
    service=TaskService(db,{'RepoMind':root},run=fake)
    try:
        task=service.prepare('RepoMind','Change a file');service.start('RepoMind',task['task_id'])
        done=wait(service,task['task_id'])
        assert done['status']=='failed' and done['changes'] and not done['candidates']
        assert recall(db,'RepoMind','mode')==[]
    finally:service.close()
