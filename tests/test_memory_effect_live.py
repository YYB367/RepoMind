"""No paid calls: fake transport, real finite loop/copies and process supervision."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from time import perf_counter

import pytest

from test_memory_effect import suite, FakeSandbox
from repomind.agent.models import ActionBatch
from repomind.agent.providers import AgentTransportError
from repomind.agent.workspace import digest
from repomind.memory_effect import load_suite, write_new
from repomind.memory_effect_live import (SERVICE, ARMS, Journal, BoundedProvider, freeze_live, load_live,
    execute_arm, run_live, supervise, recover, usage_record, usage_summary, finish_report, payload)


@pytest.fixture
def live_suite(suite,tmp_path):
    dest=tmp_path/'live'
    freeze_live(suite,dest)
    return dest


class Client:
    def __init__(self,suite,model='actual-model',missing_usage=False,broken=None):
        row=json.loads((suite/'offline-actions.jsonl').read_text(encoding='utf-8'))
        self.responses=deepcopy(row['responses']);self.calls=[]
        self.model=model;self.missing_usage=missing_usage;self.broken=broken
    def _post(self,suffix,body):
        self.calls.append(deepcopy(body))
        if self.broken=='transport':raise OSError('secret upstream body')
        response={'model':self.model,'id':'unit-response','system_fingerprint':'unit-fingerprint',
                  'choices':[{'finish_reason':'stop','message':{'content':json.dumps(self.responses[len(self.calls)-1])}}],
                  'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150,
                           'prompt_cache_hit_tokens':20,'prompt_cache_miss_tokens':80}}
        if self.missing_usage:response.pop('usage')
        if self.broken=='length':response['choices'][0]['finish_reason']='length'
        if self.broken=='schema':response['choices'][0]['message']['content']='{"actions":[]}'
        if self.broken=='missing-model':response.pop('model')
        if self.broken=='empty-choice':response['choices']=[]
        if self.broken=='whitespace':response['choices'][0]['message']['content']=' \n       \n '
        if self.broken=='output-budget':response['usage']['completion_tokens']=2049
        return response


def test_new_version_keeps_old_case_and_scoring(suite,live_suite):
    original={p.relative_to(suite).as_posix():p.read_bytes() for p in suite.rglob('*') if p.is_file()}
    load_suite(suite);load_live(live_suite)
    for name in ('task.json','memory.json','public.py','acceptance.py','system.txt','offline-actions.jsonl','repository/src/pagination.py'):
        assert (live_suite/name).read_bytes()==original[name]
    assert json.loads((live_suite/'protocol.json').read_text(encoding='utf-8'))['parent_manifest_sha256']==digest(suite/'manifest.json')
    a,b=(json.loads((live_suite/'outbound-review.json').read_text(encoding='utf-8'))['arms'][n] for n in ARMS)
    assert a['readable_files']==b['readable_files']
    pa,pb=(json.loads(x['first_request']['messages'][1]['content']) for x in (a,b))
    assert pa.pop('memory')=={'facts':[]} and len(pb.pop('memory')['facts'])==1 and pa==pb
    assert a['first_request']['max_tokens']==b['first_request']['max_tokens']==2048
    assert a['first_request']['model']==b['first_request']['model']=='deepseek-flash'


@pytest.mark.parametrize('filename',['acceptance.py','outbound-review.json','protocol.json','repository/src/pagination.py'])
def test_live_manifest_tampering_rejected(live_suite,filename):
    p=live_suite/filename;p.write_bytes(p.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='摘要'):load_live(live_suite)


def test_approval_checked_before_config_or_run_directory(live_suite,tmp_path,monkeypatch):
    monkeypatch.setattr('repomind.memory_effect_live.live_config',lambda:pytest.fail('Not authorized'))
    with pytest.raises(ValueError,match='批准'):run_live(live_suite,tmp_path/'run',tmp_path/'config','bad')
    assert not (tmp_path/'run').exists()


def test_actual_first_requests_match_exact_review_and_judge_never_sent(live_suite,tmp_path):
    clients=[]
    for name in ARMS:
        client=Client(live_suite);clients.append(client)
        result=execute_arm(live_suite,tmp_path/name,tmp_path/'config',name,client=client,sandbox=FakeSandbox())
        assert result['strict_success']==1 and result['checks_passed']==27
        assert result['model_requests']==4 and result['total_tokens']==600
        assert result['cached_input_tokens']==80 and result['resolved_models']==['actual-model']
        review=json.loads((live_suite/'outbound-review.json').read_text(encoding='utf-8'))
        assert client.calls[0]==review['arms'][name]['first_request']
        assert not any('test_acceptance.py' in json.dumps(c) or 'Scripted workflow' in json.dumps(c) for c in client.calls)
        assert len(list((tmp_path/name/'requests').glob('*.start.json')))==4
    assert clients[0].calls[0]['messages'][0]==clients[1].calls[0]['messages'][0]


@pytest.mark.parametrize('broken',['transport','length','schema','missing-model','empty-choice','output-budget','whitespace'])
def test_request_errors_stop_no_automatic_retry(live_suite,tmp_path,broken):
    client=Client(live_suite,broken=broken)
    result=execute_arm(live_suite,tmp_path/'arm',tmp_path/'config',ARMS[0],client=client,sandbox=FakeSandbox())
    assert len(client.calls)==1 and result['status']=='model_transport_error'
    assert result['infrastructure_error'] and result['strict_success']==0
    record=result['request_records'][0]
    assert record['error_type'] and 'secret upstream' not in json.dumps(record)
    if broken=='transport':assert result['total_tokens'] is None
    else:assert record['usage']['input_tokens']==100


def test_request_budget_and_context_checked_before_transmission(live_suite,tmp_path):
    review=json.loads((live_suite/'outbound-review.json').read_text(encoding='utf-8'))['arms'][ARMS[0]]
    client=Client(live_suite)
    provider=BoundedProvider(client,Journal(tmp_path/'arm'),review['messages'])
    provider.calls=[{}]*6
    with pytest.raises(AgentTransportError,match='budget'):provider.generate(review['messages'])
    provider.calls=[]
    with pytest.raises(AgentTransportError,match='context'):provider.generate([{'role':'user','content':'x'*24001}])
    with pytest.raises(AgentTransportError,match='mismatch'):provider.generate([{'role':'user','content':'changed'}])
    assert not client.calls


def test_returned_model_change_stops_and_preserves_usage(live_suite,tmp_path):
    review=json.loads((live_suite/'outbound-review.json').read_text(encoding='utf-8'))['arms'][ARMS[0]]
    client=Client(live_suite);provider=BoundedProvider(client,Journal(tmp_path),review['messages'])
    provider.generate(review['messages']);client.model='different'
    with pytest.raises(AgentTransportError,match='model'):provider.generate(review['messages'])
    assert len(client.calls)==2 and provider.calls[1]['usage']['total_tokens']==150


@pytest.mark.parametrize('raw,expected',[(None,False),({'prompt_tokens':True,'completion_tokens':1,'total_tokens':2},False),
    ({'prompt_tokens':10,'completion_tokens':2,'total_tokens':13},False),
    ({'prompt_tokens':10,'completion_tokens':2,'total_tokens':12,'prompt_cache_hit_tokens':11},False),
    ({'prompt_tokens':10,'completion_tokens':2,'total_tokens':12},True),
    ({'prompt_tokens':10,'completion_tokens':2,'total_tokens':12,'prompt_tokens_details':{'cached_tokens':3}},True)])
def test_actual_usage_validation_no_fabricated_zero(raw,expected):
    row=usage_record(raw);assert row['complete']==expected
    if not expected:assert row['total_tokens'] is None


def test_missing_usage_keeps_quality_but_cost_unknown(live_suite,tmp_path):
    result=execute_arm(live_suite,tmp_path/'arm',tmp_path/'config',ARMS[0],client=Client(live_suite,missing_usage=True),sandbox=FakeSandbox())
    assert result['checks_passed']==27 and result['strict_success']==1
    assert result['total_tokens'] is None and result['model_requests']==4


def test_interrupted_request_start_is_counted_unknown(tmp_path):
    Journal(tmp_path).start('requests',{'payload':{'messages':[]}})
    summary=usage_summary(tmp_path)
    assert summary['model_requests']==1 and summary['total_tokens'] is None
    assert summary['request_records'][0]['error_type']=='request_interrupted_usage_unknown'


def test_torn_receipt_remains_unknown_and_original_is_preserved(tmp_path):
    path=Journal(tmp_path).start('requests',{'payload':{'messages':[]}})
    path.with_suffix('.end.json').write_text('{"usage":',encoding='utf-8')
    assert usage_summary(tmp_path)['total_tokens'] is None
    assert path.with_suffix('.end.json').read_text()=='{"usage":'


def test_simulation_cannot_construct_http_client(live_suite,tmp_path,monkeypatch):
    monkeypatch.setattr('repomind.memory_effect_live.OpenAICompatibleProvider',lambda *_:pytest.fail('No model client in simulation'))
    arm=execute_arm(live_suite,tmp_path/'arm',tmp_path/'config',ARMS[0],sandbox=FakeSandbox(),simulation=True)
    report={'kind':'protocol_simulation','arms':[arm],'status':'completed'}
    finish_report(report)
    assert report['new_model_requests']==0 and report['actual_tokens'] is None
    assert arm['simulated_requests']==4 and arm['model_requests']==0
    assert not arm['claim']['is_model_claim'] and report['verdict']['direction']=='not_measured'


def test_supervisor_hard_deadline_kills_owned_process_and_retains_start(tmp_path):
    script="import time;from pathlib import Path;Path('"+str(tmp_path/'evidence.txt').replace('\\','/')+"').write_text('before timeout');time.sleep(10)"
    started=perf_counter()
    assert supervise([sys.executable,'-c',script],tmp_path,1)=='time_limit'
    assert perf_counter()-started<5
    assert (tmp_path/'evidence.txt').read_text()=='before timeout'
    assert json.loads((tmp_path/'worker-end.json').read_text())['status']=='time_limit'


def test_pair_preserves_first_result_and_uses_two_independent_copies(live_suite,tmp_path):
    clients=[]
    def supervisor(args,directory,seconds):
        assert seconds==300
        client=Client(live_suite);clients.append(client)
        execute_arm(args[4],directory,args[6],args[7],args[8] or None,client=client,sandbox=FakeSandbox())
        return 'exited'
    dest=tmp_path/'run'
    report=run_live(live_suite,dest,tmp_path/'config',digest(live_suite/'outbound-review.json'),supervisor=supervisor,sandbox=FakeSandbox(),check_config=False)
    assert report['status']=='completed' and report['initial_files_identical']
    assert report['new_model_requests']==8 and report['actual_tokens']==1200
    assert report['verdict']['direction']=='equal' # Synthetic counts, never a real experiment.
    assert report['comparability']['returned_models_match']
    initial=(dest/'first-start.json').read_bytes();final=(dest/'final-report.json').read_bytes()
    with pytest.raises(ValueError,match='新目录'):
        run_live(live_suite,dest,tmp_path/'config',digest(live_suite/'outbound-review.json'),check_config=False)
    assert (dest/'first-start.json').read_bytes()==initial and (dest/'final-report.json').read_bytes()==final


def test_pair_timeout_preserves_partial_usage_and_stops_second(live_suite,tmp_path):
    calls=[]
    def timeout(args,directory,seconds):
        calls.append(directory);Journal(directory).start('requests',{'payload':{'model':'unit'}})
        return 'time_limit'
    report=run_live(live_suite,tmp_path/'run',tmp_path/'config',digest(live_suite/'outbound-review.json'),supervisor=timeout,sandbox=FakeSandbox(),check_config=False)
    assert len(calls)==1 and report['status']=='failed' and report['new_model_requests']==1
    assert report['verdict']['direction']=='inconclusive' and report['actual_tokens'] is None
    assert report['arms'][0]['evidence_incomplete']


def test_interrupt_after_request_retains_receipt(live_suite,tmp_path):
    def interrupt(args,directory,seconds):
        Journal(directory).start('requests',{'payload':{'model':'unit'}})
        raise KeyboardInterrupt()
    run=tmp_path/'run'
    report=run_live(live_suite,run,tmp_path/'config',digest(live_suite/'outbound-review.json'),supervisor=interrupt,sandbox=FakeSandbox(),check_config=False)
    assert report['status']=='interrupted' and report['new_model_requests']==1
    assert (run/'final-report.json').is_file()


def test_different_fingerprints_make_result_inconclusive(live_suite,tmp_path):
    arm=execute_arm(live_suite,tmp_path/'arm',tmp_path/'config',ARMS[0],client=Client(live_suite),sandbox=FakeSandbox())
    other=deepcopy(arm);other.update(name=ARMS[1],system_fingerprints=['changed'])
    report={'arms':[arm,other],'status':'completed','initial_files_identical':True}
    finish_report(report)
    assert report['verdict']['direction']=='inconclusive'


def test_recovery_never_calls_model_and_requires_worker_stop(live_suite,tmp_path,monkeypatch):
    run=tmp_path/'run';run.mkdir()
    write_new(run/'first-start.json',{'frozen':{'image':'sha256:'+'a'*64},'arms':[],'status':'running'})
    write_new(run/'a/worker-start.json',{'pid':123})
    Journal(run/'a').start('requests',{'payload':{'model':'unit'}})
    monkeypatch.setattr('repomind.memory_effect_live.OpenAICompatibleProvider',lambda *_:pytest.fail('Recovery cannot call models'))
    with pytest.raises(ValueError,match='worker'):recover(run,tmp_path/'config')
    report=recover(run,tmp_path/'config',worker_stopped=True)
    assert report['status']=='interrupted' and report['new_model_requests']==1 and report['actual_tokens'] is None
    with pytest.raises(ValueError,match='最终'):recover(run,tmp_path/'config',worker_stopped=True)
