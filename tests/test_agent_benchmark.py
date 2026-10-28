import json
from pathlib import Path
import pytest

from repomind.agent import benchmark
from repomind.agent.models import AgentBudget
from repomind.agent.providers import ReplayAgentProvider
from repomind.cli import main
from repomind.platform.tracing import TraceOutbox

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/v2'
IMAGE='sha256:'+'a'*64


class FakeSandbox:
    def __init__(self,*args,**kwargs): pass
    def probe(self): return {'backend':'unit_test_double','actual_docker_isolation':False}
    def run_tests(self,root,*,expected_count,judge_dir=None):
        return {'passed':True,'test_report':{'collected':expected_count,'passed':expected_count,'failed':0,'errors':0,'skipped':0,'exit_code':0},
                'infrastructure_error':False,'cleanup_verified':True,'elapsed_seconds':.01,'stdout':'unit fake','exit_code':0}


def test_benchmark_experience_only_after_success_and_hidden_gold_not_in_model_context(tmp_path,monkeypatch):
    monkeypatch.setattr(benchmark,'DockerSandbox',FakeSandbox)
    captured=[]
    class Capturing(ReplayAgentProvider):
        def generate(self,messages):
            captured.append(json.dumps(messages,ensure_ascii=False))
            return super().generate(messages)
    monkeypatch.setattr(benchmark,'_provider',lambda mode,root,task:Capturing(root/'recorded-actions.jsonl',task.task_id))
    report=benchmark.run_developer_benchmark(DATA/'dev/tasks.jsonl',tmp_path/'report.json',image=IMAGE,
        config_dir=tmp_path/'docker',data_root=DATA,state_dir=tmp_path/'state',run_id='unit-run')
    assert report['validation']['completed_without_errors']
    assert report['validation']['scripted_results_are_not_model_accuracy']
    for arm in report['variants'].values():
        assert arm['metrics']['successful_tasks']==6 and arm['metrics']['model_requests']==0
    enhanced=report['variants']['enhanced']['trials']
    assert not enhanced[0]['context']['experiences']
    assert enhanced[1]['context']['experiences'][0]['task_id']=='dev-01'
    assert all(row['experience_written'] for row in enhanced)
    assert all(not row['context']['experiences'] for row in report['variants']['memory']['trials'])
    assert all('acceptance_test' not in text and '/judge/' not in text for text in captured)
    traces=TraceOutbox(report['outbox']).records()
    assert len(traces)==18 and {t.stage for t in traces}=={'developer_task'}
    assert all('memory' not in t.input for t in traces)
    assert all(not row['hidden_grading_fed_back_to_model'] for arm in report['variants'].values() for row in arm['trials'])
    with pytest.raises(ValueError,match='fresh'):
        benchmark.run_developer_benchmark(DATA/'dev/tasks.jsonl',tmp_path/'report.json',image=IMAGE,
            config_dir=tmp_path/'docker',data_root=DATA,state_dir=tmp_path/'state',run_id='unit-run')


def test_no_model_call_when_docker_probe_fails(tmp_path,monkeypatch):
    class Unavailable(FakeSandbox):
        def probe(self): raise ValueError('docker unavailable')
    monkeypatch.setattr(benchmark,'DockerSandbox',Unavailable)
    monkeypatch.setattr(benchmark,'_provider',lambda *args:pytest.fail('no provider before isolation'))
    with pytest.raises(ValueError,match='docker unavailable'):
        benchmark.run_developer_benchmark(DATA/'dev/tasks.jsonl',tmp_path/'report.json',image=IMAGE,
            config_dir=tmp_path/'docker',data_root=DATA,state_dir=tmp_path/'state')
    assert not (tmp_path/'report.json').exists()


def test_guest_quality_failure_is_measured_without_faking_host_failure(tmp_path,monkeypatch):
    class Failing(FakeSandbox):
        def run_tests(self,root,*,expected_count,judge_dir=None):
            row=super().run_tests(root,expected_count=expected_count,judge_dir=judge_dir)
            if judge_dir:
                row.update(passed=False,exit_code=1)
            return row
    monkeypatch.setattr(benchmark,'DockerSandbox',Failing)
    report=benchmark.run_developer_benchmark(DATA/'dev/tasks.jsonl',tmp_path/'report.json',image=IMAGE,
        config_dir=tmp_path/'docker',data_root=DATA,state_dir=tmp_path/'state',variants=['enhanced'])
    assert report['validation']['completed_without_errors']
    arm=report['variants']['enhanced']
    assert arm['metrics']['successful_tasks']==0
    assert all(not row['experience_written'] and not row['context']['experiences'] for row in arm['trials'])


def test_cli_agent_run_routes_parameters_and_does_not_gate_on_quality(tmp_path,monkeypatch,capsys):
    calls=[]
    def fake(dataset,output,**kwargs):
        calls.append((dataset,output,kwargs))
        return {'validation':{'completed_without_errors':True},'variants':{'baseline':{'metrics':{'task_success_rate':0}}},'outbox':'outbox.jsonl'}
    monkeypatch.setattr(benchmark,'run_developer_benchmark',fake)
    assert main(['agent-bench','--dataset','tasks.jsonl','--output',str(tmp_path/'report.json'),'--image',IMAGE,'--provider','live','--max-turns','4'])==0
    assert calls[0][2]['budget']==AgentBudget(max_turns=4)
    assert calls[0][2]['provider_mode']=='live'
    assert json.loads(capsys.readouterr().out)['variants']['baseline']['task_success_rate']==0


def test_cli_doctor_requires_an_explicit_prepared_image(tmp_path,monkeypatch,capsys):
    assert main(['agent-doctor','--sandbox-config',str(tmp_path/'missing.json')])==2
    assert 'agent-prepare' in capsys.readouterr().err
