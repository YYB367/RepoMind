import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from repomind.agent.models import ActionBatch,AgentBudget,relative_path
from repomind.agent.workspace import TaskWorkspace,ToolDenied,git_env
from repomind.agent.benchmark import load_tasks,verified_manifest
from repomind.agent.memory import ExperienceStore,memory_context
from repomind.agent.providers import ReplayAgentProvider,LiveAgentProvider
from repomind.agent.loop import run_agent
from repomind.agent.sandbox import DockerSandbox,limited_process
from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.intelligence.providers import ProviderConfig

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/v2'
IMAGE='sha256:'+'a'*64

@pytest.fixture
def task():
    return load_tasks(DATA/'dev/tasks.jsonl')[0]

@pytest.fixture
def workspace(tmp_path,task):
    return TaskWorkspace(tmp_path/'repo',task,DATA)

@pytest.mark.parametrize('payload',[
    {'actions':[{'tool':'shell','command':'whoami'}]},
    {'actions':[{'tool':'run_tests','args':'--something'}]},
    {'actions':[{'tool':'finish','summary':'ok'},{'tool':'git_diff'}]},
    {'actions':[]},
    {'actions':[{'tool':'read_file','path':'x','max_lines':10000}]},
])
def test_action_schema_rejects_extra_capabilities(payload):
    with pytest.raises(ValidationError): ActionBatch.model_validate(payload)

@pytest.mark.parametrize('path',['../secret','/etc/passwd','C:/key','src\\x.py','src/a.py:stream',
    'src/../a.py','src//x.py','src/CON.py','src/NUL','src/a.','src/./a.py'])
def test_paths_are_component_checked(path):
    with pytest.raises(ValueError): relative_path(path)

def test_workspace_only_edits_declared_source_and_retains_diff(workspace,task):
    assert 'tests/test_public.py' in workspace.list_files()['files']
    path=task.writable_paths[0]
    workspace.write_file(path,'def money_minor(amount):\n    return 0\n')
    assert workspace.changed_files()==[path]
    assert '+    return 0' in workspace.git_diff()['diff']
    assert workspace.protected_integrity()
    for forbidden in ['tests/test_public.py','.git/config','README.md','../secret','.env']:
        with pytest.raises(ToolDenied): workspace.write_file(forbidden,'changed')
    with pytest.raises(ToolDenied): workspace.read_file('../secret')

def test_protected_files_cannot_be_silently_replaced(workspace):
    (workspace.root/'tests/test_public.py').write_text('pass',encoding='utf-8')
    with pytest.raises(ToolDenied): workspace.list_files()

def test_hardlink_cannot_reach_an_outside_file(workspace,tmp_path,task):
    outside=tmp_path/'outside.py'
    outside.write_text('private marker',encoding='utf-8')
    target=workspace.root/task.writable_paths[0]
    target.unlink()
    try: os.link(outside,target)
    except OSError: pytest.skip('hardlinks unavailable on this filesystem')
    with pytest.raises(ToolDenied): workspace.write_file(task.writable_paths[0],'overwrite')
    assert outside.read_text(encoding='utf-8')=='private marker'

def test_git_subprocess_does_not_inherit_model_keys(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY','private-unit-marker')
    assert 'DEEPSEEK_API_KEY' not in git_env()
    assert git_env()['GIT_CONFIG_NOSYSTEM']=='1'


def test_unregistered_or_even_manifest_listed_credentials_never_reach_task_copy(tmp_path,task):
    import shutil
    data=tmp_path/'data'
    shutil.copytree(DATA,data)
    (data/'repository/.env').write_text('PRIVATE_MARKER=not-for-model',encoding='utf-8')
    copy=TaskWorkspace(tmp_path/'safe-repo',task,data)
    assert '.env' not in copy.list_files()['files'] and not (copy.root/'.env').exists()
    manifest=json.loads((data/'manifest.json').read_text(encoding='utf-8'))
    manifest['files']['repository/.env']={'sha256':'irrelevant','bytes':0}
    (data/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    with pytest.raises(ToolDenied,match='forbidden repository file'):
        TaskWorkspace(tmp_path/'blocked-repo',task,data)

def test_manifest_detects_changed_inputs(tmp_path):
    import shutil
    shutil.copytree(DATA,tmp_path/'data')
    (tmp_path/'data/events.jsonl').write_text('\n',encoding='utf-8')
    with pytest.raises(ValueError,match='frozen manifest'): verified_manifest(tmp_path/'data')

def test_current_vs_temporal_memory_and_experience_scope(tmp_path):
    tasks=load_tasks(DATA/'dev/tasks.jsonl')
    shipping=tasks[1]
    experiences=ExperienceStore(tmp_path/'experience.sqlite3')
    experiences.add(project_id='ParcelKit',category='money',task_id='previous',summary='validated public workflow',source_run='r',sequence=0)
    experiences.add(project_id='ShadowKit',category='shipping',task_id='other',summary='must not leak',source_run='r',sequence=0)
    experiences.add(project_id='ParcelKit',category='shipping',task_id='future',summary='not yet done',source_run='r',sequence=5)
    with SQLiteMemoryStore(':memory:') as store:
        store.import_jsonl(DATA/'events.jsonl')
        current=memory_context(shipping,'memory',store,experiences,sequence=1,current_as_of='2026-10-01')
        enhanced=memory_context(shipping,'enhanced',store,experiences,sequence=1,current_as_of='2026-10-01')
        assert json.loads(current['facts'][0]['value'])['step_grams']==250
        assert json.loads(enhanced['facts'][0]['value'])['step_grams']==500
        assert [e['task_id'] for e in enhanced['experiences']]==['previous']
        assert not current['experiences']
        assert not memory_context(shipping,'baseline',store,experiences,sequence=1,current_as_of='2026-10-01')['facts']
    experiences.close()

class FakeSandbox:
    def __init__(self,passed=True): self.passed=passed; self.calls=0
    def run_tests(self,root,*,expected_count):
        self.calls+=1
        return {'passed':self.passed,'infrastructure_error':False,'test_report':{'collected':expected_count}}

def test_replay_loop_uses_real_file_tools_without_gold_feedback(workspace,task):
    provider=ReplayAgentProvider(DATA/'recorded-actions.jsonl',task.task_id)
    sandbox=FakeSandbox()
    result=run_agent(task,workspace,provider,sandbox,{'mode':'baseline','facts':[],'experiences':[]})
    assert result['status']=='finished' and result['changed_files']==task.writable_paths
    assert sandbox.calls==1 and result['model']['request_count']==0
    assert 'scripted' in result['model']['validation_kind']
    assert [o['tool'] for o in result['observations']]==['read_file','read_file','write_file','run_tests','git_diff','finish']

def test_loop_test_and_turn_budgets_cannot_be_bypassed(workspace,task):
    class Repeated:
        def generate(self,messages): return ActionBatch.model_validate({'actions':[{'tool':'run_tests'}]})
        def safe_metadata(self): return {'request_count':0,'usage':{}}
    sandbox=FakeSandbox(False)
    result=run_agent(task,workspace,Repeated(),sandbox,{},budget=AgentBudget(max_turns=4,max_test_runs=1))
    assert result['status']=='turn_budget_exhausted' and sandbox.calls==1
    assert result['blocked_actions']==3 and result['public_test_failures']==1

def test_live_telemetry_freezes_actual_message_history(monkeypatch):
    provider=LiveAgentProvider(ProviderConfig(base_url='https://unit.invalid',api_key='synthetic-test-key',chat_model='test',api_style='deepseek'))
    seen=[]
    def post(suffix,payload):
        seen.append(payload)
        provider.client.request_count+=1
        provider.client.usage={'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}
        provider.client.usage_report_counts={k:1 for k in provider.client.usage}
        return {'model':'actual-test-model','choices':[{'finish_reason':'stop','message':{'content':'{"actions":[{"tool":"finish","summary":"done"}]}'}}]}
    monkeypatch.setattr(provider.client,'_post',post)
    messages=[{'role':'user','content':'public task'}]
    provider.generate(messages)
    messages.append({'role':'user','content':'future tool result'})
    assert len(provider.calls[0]['input'])==1 and provider.calls[0]['usage_complete']
    assert seen[0]['response_format']=={'type':'json_object'}
    assert seen[0]['thinking']=={'type':'disabled'}
    assert 'synthetic-test-key' not in json.dumps(provider.safe_metadata())

def test_docker_arguments_are_fixed_local_and_limited(workspace,tmp_path):
    sandbox=DockerSandbox(IMAGE,tmp_path/'config')
    args=sandbox.run_args(workspace.root,name='repomind-v2-test',owner='test')
    for flag in ['--pull=never','--network=none','--ipc=none','--read-only','--cap-drop=ALL','--memory=256m','--pids-limit=64']:
        assert flag in args
    assert all('readonly' in args[i+1] for i,x in enumerate(args) if x=='--mount')
    assert '65532:65532' in args and args[-1]=='/workspace/tests/test_public.py'
    with pytest.raises(ValueError): DockerSandbox('python:latest',tmp_path/'config')
    with pytest.raises(ValueError): DockerSandbox(IMAGE,tmp_path/'config',engine_host='tcp://remote:2375')

def test_bounded_process_stops_output_and_time():
    result=limited_process([sys.executable,'-c',"import os; os.write(1,b'x'*100000)"],timeout=5,max_bytes=4096)
    assert len(result['stdout'])<=4096 and result['limit_reason']=='output_limit'
    result=limited_process([sys.executable,'-c','import time; time.sleep(10)'],timeout=.15,max_bytes=4096)
    assert result['limit_reason']=='timeout'

@pytest.mark.parametrize('kind',['profile','early_exit','timeout','output_limit'])
def test_real_container_boundary(tmp_path,kind):
    image=os.getenv('REPOMIND_TEST_AGENT_IMAGE')
    if not image: pytest.skip('set REPOMIND_TEST_AGENT_IMAGE to run real Docker isolation tests')
    repo=tmp_path/'repo'
    (repo/'tests').mkdir(parents=True)
    (repo/'README.md').write_text('readonly marker',encoding='utf-8')
    profile='''import os, socket, pathlib, resource
def test_profile():
    assert os.getuid() == 65532
    assert resource.getrlimit(resource.RLIMIT_NOFILE) == (256, 256)
    assert not pathlib.Path('/var/run/docker.sock').exists()
    assert all(name not in os.environ for name in ['DEEPSEEK_API_KEY','LANGFUSE_SECRET_KEY','OPENAI_API_KEY'])
    assert pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip() == '268435456'
    assert pathlib.Path('/sys/fs/cgroup/pids.max').read_text().strip() == '64'
    status = pathlib.Path('/proc/self/status').read_text()
    assert 'NoNewPrivs:\\t1' in status
    assert 'CapEff:\\t0000000000000000' in status
    for path in ['/etc/repomind-probe','/workspace/README.md']:
        try: pathlib.Path(path).write_text('blocked')
        except OSError: pass
        else: assert False, 'read-only boundary missing'
    pathlib.Path('/tmp/writable-probe').write_text('ok')
    try: socket.create_connection(('1.1.1.1',80),timeout=.5)
    except OSError: pass
    else: assert False, 'external network unexpectedly reachable'
'''
    bodies={'profile':profile,'early_exit':'import os\nos._exit(0)\n',
            'timeout':'def test_spin():\n    while True: pass\n',
            'output_limit':"def test_loud(capfd):\n    with capfd.disabled():\n        import os\n        os.write(1,b'x'*1000000)\n"}
    (repo/'tests/test_public.py').write_text(bodies[kind],encoding='utf-8')
    sandbox=DockerSandbox(image,tmp_path/'config',timeout_seconds=3 if kind=='timeout' else 20,max_output_bytes=4096 if kind=='output_limit' else 65536)
    result=sandbox.run_tests(repo,expected_count=1)
    assert result['cleanup_verified']
    if kind=='profile': assert result['passed'],result
    else:
        assert not result['passed']
        assert result['execution_error']==('invalid_guest_result' if kind=='early_exit' else kind)
