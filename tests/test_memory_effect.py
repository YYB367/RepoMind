from contextlib import contextmanager
import json
from pathlib import Path
import threading

import pytest

from repomind.cli import main
from repomind.memory_effect import freeze_case, load_suite, run_offline, effect_verdict, ComparisonReports
from repomind.web.server import WorkbenchServer
from test_workbench import request


IMAGE='sha256:'+'a'*64


@pytest.fixture
def suite(tmp_path,monkeypatch):
    root=tmp_path/'root';root.mkdir()
    source=Path(__file__).parents[1]/'src/repomind/workbench.py'
    def git(_root,*args):
        return source.read_bytes() if args[0]=='show' else b'a'*40
    monkeypatch.setattr('repomind.web.evidence.git',git)
    monkeypatch.setattr('repomind.memory_effect.recall',lambda *_:[{'subject':'workbench.page','field':'pagination_validation',
        'value':'offset excludes bool; limit 1 to 100','source_id':'confirmed-source','path':str(root/'docs/adr.md'),'sha256':'b'*64}])
    dest=tmp_path/'suite'
    freeze_case(root,tmp_path/'ledger.sqlite3',dest,IMAGE)
    return dest


class FakeSandbox:
    """Protocol-only test double; no claim to execute the acceptance source."""
    def __init__(self,fail=False):self.calls=[];self.fail=fail
    def probe(self):return {'backend':'unit_double','actual_docker_isolation':False}
    def run_tests(self,repo,*,expected_count,judge_dir=None):
        self.calls.append((repo,expected_count,judge_dir))
        passed=0 if self.fail else expected_count
        return {'passed':not self.fail,'infrastructure_error':False,'execution_error':None,'cleanup_verified':True,'exit_code':int(self.fail),
                'stdout':'unit-only','test_report':{'collected':expected_count,'passed':passed,'failed':expected_count-passed,'errors':0,'skipped':0,'exit_code':int(self.fail)}}


def test_freeze_payload_is_equal_except_memory_and_excludes_judge_and_solution(suite):
    data=json.loads((suite/'outbound-review.json').read_text(encoding='utf-8'))
    a,b=(data['arms'][n] for n in ('without_memory','with_memory'))
    assert a['readable_files']==b['readable_files']
    pa,pb=(json.loads(x['messages'][1]['content']) for x in (a,b))
    assert pa.pop('memory')=={'facts':[]} and pb.pop('memory')['facts'][0]['source_id']=='confirmed-source'
    assert pa==pb and a['messages'][0]==b['messages'][0]
    assert not any('acceptance' in n or 'offline-actions' in n for n in a['readable_files'])
    assert 'def page_query' in a['readable_files']['src/pagination.py']
    assert data['service']['max_requests_total']==12


@pytest.mark.parametrize('name',['protocol.json','acceptance.py','public.py','memory.json','offline-actions.jsonl','repository/src/pagination.py','outbound-review.json'])
def test_any_frozen_file_tampering_is_rejected(suite,name):
    path=suite/name;path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='摘要'):load_suite(suite)


def test_replay_preserves_empty_baseline_and_immutable_inputs(suite,tmp_path,monkeypatch):
    monkeypatch.setattr('repomind.intelligence.providers.OpenAICompatibleProvider._post',lambda *_:pytest.fail('No network request permitted'))
    from repomind.agent.providers import ReplayAgentProvider
    captured=[]
    class Recording(ReplayAgentProvider):
        def generate(self,messages):
            if self.position==0:captured.append(json.loads(json.dumps(messages)))
            return super().generate(messages)
    monkeypatch.setattr('repomind.memory_effect.ReplayAgentProvider',Recording)
    sandbox=FakeSandbox();run=tmp_path/'run';report=run_offline(suite,run,tmp_path/'config',sandbox=sandbox)
    assert report['status']=='completed' and report['initial_files_identical']
    a,b=report['arms'];assert a['memory_input']==[] and b['memory_input'][0]['source_id']=='confirmed-source'
    assert a['initial_code_hashes']==b['initial_code_hashes']
    assert a['strict_success']==b['strict_success']==1 and a['checks_total']==27
    assert report['verdict']['direction']=='not_measured' and report['actual_tokens'] is None
    assert all(x['total_tokens'] is None and x['model_requests']==0 for x in report['arms'])
    assert a['claim']['is_model_claim'] is False and len(sandbox.calls)==6
    outbound=json.loads((suite/'outbound-review.json').read_text(encoding='utf-8'))
    for index, name in enumerate(['without_memory','with_memory']):
        stored=json.loads((run/('a' if index==0 else 'b')/'input.json').read_text(encoding='utf-8'))
        assert stored['messages']==captured[index]==outbound['arms'][name]['messages']
    assert sandbox.calls[2][2] is not None and sandbox.calls[-1][2] is not None
    initial=(run/'first-start.json').read_bytes()
    with pytest.raises(ValueError,match='新目录'):run_offline(suite,run,tmp_path/'config',sandbox=sandbox)
    assert (run/'first-start.json').read_bytes()==initial


def test_sandbox_failure_preserves_partial_report(suite,tmp_path):
    class Broken(FakeSandbox):
        def run_tests(self,*args,**kwargs):
            row=super().run_tests(*args,**kwargs);row['infrastructure_error']=True;return row
    report=run_offline(suite,tmp_path/'run',tmp_path/'config',sandbox=Broken())
    assert report['status']=='failed' and len(report['arms'])==1
    assert (tmp_path/'run/report.json').exists()
    assert report['verdict']['direction']=='not_measured'


@pytest.mark.parametrize('strict,checks,tokens,expected',[(1,27,80,'improved'),(1,27,100,'equal'),(0,26,120,'decreased'),(0,26,80,'mixed'),(1,27,None,'inconclusive')])
def test_real_direction_logic_is_separate_from_offline_examples(strict,checks,tokens,expected):
    arms=[{'strict_success':1,'checks_passed':27,'total_tokens':100},
          {'strict_success':strict,'checks_passed':checks,'total_tokens':tokens}]
    assert effect_verdict(arms,real=True)['direction']==expected
    assert effect_verdict(arms,real=False)['direction']=='not_measured'
    assert effect_verdict(arms,real=True,comparable=False)['direction']=='inconclusive'


def test_http_projection_is_project_scoped_read_only_and_escaped(suite,tmp_path):
    report=run_offline(suite,tmp_path/'runs/first',tmp_path/'config',sandbox=FakeSandbox())
    with WorkbenchServer(tmp_path/'absent.sqlite3',0,comparison_dir=tmp_path/'runs') as server:
        server.comparison_only=True
        t=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01});t.start()
        try:
            assert request(server,'/comparisons')[0]==200
            assert request(server,'/static/comparisons.js')[0]==200
            assert request(server,'/api/memory-comparisons?project=RepoMind')[1]['items'][0]['id']==report['id']
            assert request(server,'/api/memory-comparisons?project=Other')[1]['items']==[]
            assert request(server,'/api/memory-comparisons/'+report['id']+'?project=Other')[0]==404
            assert request(server,'/api/tasks/prepare',{'project':'RepoMind','prompt':'do not run'})[0]==403
        finally:server.shutdown();t.join()
    assert not (tmp_path/'absent.sqlite3').exists()


def test_reports_reject_oversized_and_outside_paths(tmp_path):
    root=tmp_path/'reports';(root/'large').mkdir(parents=True)
    (root/'large/report.json').write_bytes(b' '*(4*1024*1024+1))
    assert ComparisonReports(root).list('RepoMind')==[]
    with pytest.raises(ValueError):ComparisonReports(root).get('RepoMind','../../private')


def test_live_entrypoint_is_not_exposed(capsys):
    with pytest.raises(SystemExit):main(['memory-compare','offline','--run-dir','unused','--live'])
