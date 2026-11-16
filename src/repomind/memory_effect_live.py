"""V4.4.1 opt-in live pair. Old V4.4 code and inputs remain executable unchanged.

The coordinator never sends model requests. Each arm runs in a supervised child;
immutable request/tool starts survive termination, including unknown usage.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from uuid import uuid4

from repomind.agent.loop import run_agent
from repomind.agent.models import ActionBatch, AgentBudget, AgentTask
from repomind.agent.providers import SYSTEM_PROMPT, PROMPT_SHA256, AgentTransportError
from repomind.agent.sandbox import DockerSandbox
from repomind.agent.workspace import TaskWorkspace, checked_path, digest
from repomind.codex_activity import safe_text
from repomind.intelligence.providers import ProviderConfig, OpenAICompatibleProvider, _json_loads
from repomind.memory_effect import encode, write_new, load_suite, initial_input, effect_verdict, implementation_hashes

GOAL = 'V4.4.1：同条件真实模型双组记忆效果对照；保留首次结果和实际用量'
ARMS = ('without_memory', 'with_memory')
SERVICE = {'endpoint': 'https://api.deepseek.com/chat/completions', 'model': 'deepseek-flash',
           'temperature': 0, 'thinking': 'disabled', 'max_completion_tokens': 2048,
           'max_requests_per_arm': 6, 'max_requests_total': 12, 'max_output_tokens_total': 24576,
           'max_context_chars_per_request': 24000, 'max_request_bytes': 120000,
           'max_response_bytes': 1000000, 'request_timeout_seconds': 60,
           'wall_seconds_per_arm': 300, 'automatic_retry': False,
           'input_tokens': 'Unknown until actual usage; character bounds are not Token counts.'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def hashes():
    root = Path(__file__).parent
    return implementation_hashes() | {name: digest(root/name) for name in (
        'memory_effect_live.py', 'memory_effect_cli.py', 'intelligence/providers.py',
        'intelligence/config.py', 'codex_activity.py', 'platform/tracing.py')}


def snapshot(path, value):
    """Only derived progress is replaced. Original starts/receipts are exclusive."""
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    temporary.write_bytes(encode(value))
    temporary.replace(path)


def safe(value):
    if isinstance(value, str): return safe_text(value, 1000000)
    if isinstance(value, list): return [safe(v) for v in value]
    if isinstance(value, dict): return {k: safe(v) for k, v in value.items()}
    return value


def freeze_live(parent, output):
    """Rebind implementation, never regenerate memory, task, source or scoring."""
    parent, original, task = load_suite(parent)
    output = Path(output).resolve()
    if output.exists(): raise ValueError('新版本冻结目录必须不存在。')
    old_manifest = json.loads((parent/'manifest.json').read_text(encoding='utf-8'))
    files = {name: checked_path(parent, name).read_bytes() for name in old_manifest['files']
             if name not in {'protocol.json', 'outbound-review.json'}}
    protocol = deepcopy(original)
    protocol.update(stage_goal=GOAL, schema=2, frozen_at=stamp(), implementation_hashes=hashes(),
                    parent_manifest_sha256=digest(parent/'manifest.json'), proposed_live=SERVICE)
    files['protocol.json'] = encode(protocol)
    outbound = json.loads((parent/'outbound-review.json').read_text(encoding='utf-8'))
    outbound.update(stage_goal=GOAL+'；待用户授权，尚未发送', service=SERVICE,
                    protocol_sha256=hashlib.sha256(files['protocol.json']).hexdigest())
    for arm in ARMS:
        messages = outbound['arms'][arm]['messages']
        outbound['arms'][arm]['first_request'] = payload(messages)
    outbound['continuation_policy'] = {
        'sent': ['Earlier messages and generated action JSON',
                 'Only allowlisted source/public-test reads, tool results, public output and source diff'],
        'never_sent': outbound['excluded'],
        'bounds': 'At most 24000 serialized message characters per request, 120000 UTF-8 body bytes; no truncation to fit.',
        'unknown_before_execution': 'Future generated source and tool feedback; exact requests journalled before sending.'}
    files['outbound-review.json'] = encode(outbound)
    files['upgrade-input.json'] = encode({'stage_goal': GOAL, 'parent_manifest_sha256': digest(parent/'manifest.json'),
        'preserved_file_hashes': {n: hashlib.sha256(b).hexdigest() for n,b in files.items()
                                 if n not in {'protocol.json','outbound-review.json'}},
        'change': 'Bind tested live execution; explicitly select currently documented deepseek-flash. No scoring changes.'})
    output.mkdir(parents=True)
    for name, body in files.items(): write_new(output/name, body)
    write_new(output/'manifest.json', {'stage_goal': GOAL, 'files': {n: {'sha256': hashlib.sha256(b).hexdigest()} for n,b in files.items()}})
    load_live(output)
    return {'suite': str(output), 'review_sha256': digest(output/'outbound-review.json'),
            'manifest_sha256': digest(output/'manifest.json'), 'new_model_requests': 0}


def payload(messages):
    return {'model': SERVICE['model'], 'messages': deepcopy(messages), 'response_format': {'type': 'json_object'},
            'max_tokens': SERVICE['max_completion_tokens'], 'temperature': 0, 'thinking': {'type': 'disabled'}}


def load_live(suite):
    suite = Path(suite).resolve()
    manifest = json.loads(checked_path(suite, 'manifest.json').read_text(encoding='utf-8'))
    for name, row in manifest['files'].items():
        if digest(checked_path(suite, name)) != row['sha256']: raise ValueError('冻结输入摘要不匹配。')
    protocol = json.loads((suite/'protocol.json').read_text(encoding='utf-8'))
    if protocol['schema'] != 2 or protocol['implementation_hashes'] != hashes():
        raise ValueError('真实执行实现与冻结版本不同；另建新版本，保留首次证据。')
    if protocol['proposed_live'] != SERVICE or protocol['budget'] != AgentBudget().model_dump() or protocol['system_sha256'] != PROMPT_SHA256:
        raise ValueError('执行预算或系统提示与已审核协议不同。')
    task = AgentTask.model_validate_json((suite/'task.json').read_text(encoding='utf-8'))
    review = json.loads((suite/'outbound-review.json').read_text(encoding='utf-8'))
    facts = json.loads((suite/'memory.json').read_text(encoding='utf-8'))
    for name, memory in zip(ARMS, [[], facts]):
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': json.dumps(initial_input(task, memory, protocol['budget']), ensure_ascii=False)}]
        if review['arms'][name]['first_request'] != payload(messages) or review['arms'][name]['messages'] != messages:
            raise ValueError('确切发送清单与实际初始消息不同。')
    return suite, protocol, task


def usage_record(raw):
    """Validate service counts; never turn absent or partial usage into zero."""
    raw = raw if isinstance(raw, dict) else {}
    def number(key):
        v = raw.get(key)
        return v if type(v) is int and v >= 0 else None
    inp, out, total = (number(k) for k in ('prompt_tokens','completion_tokens','total_tokens'))
    cached = number('prompt_cache_hit_tokens')
    details = raw.get('prompt_tokens_details')
    nested = details.get('cached_tokens') if isinstance(details, dict) else None
    nested = nested if type(nested) is int and nested >= 0 else None
    if cached is None: cached = nested
    valid = inp is not None and out is not None and total == inp + out
    if cached is not None and (inp is None or cached > inp): valid = False
    if nested is not None and cached != nested: valid = False
    miss = number('prompt_cache_miss_tokens')
    if cached is not None and miss is not None and inp != cached + miss: valid = False
    return {'input_tokens': inp, 'output_tokens': out, 'total_tokens': total if valid else None,
            'cached_input_tokens': cached, 'complete': valid,
            'raw': {k: raw[k] for k in ('prompt_tokens','completion_tokens','total_tokens','prompt_cache_hit_tokens',
                                      'prompt_cache_miss_tokens','prompt_tokens_details','completion_tokens_details') if k in raw}}


class Journal:
    def __init__(self, root): self.root=Path(root); self.counts={}

    def start(self, kind, data):
        index = self.counts.get(kind, 0) + 1; self.counts[kind]=index
        path = self.root/kind/('%03d'%index)
        write_new(path.with_suffix('.start.json'), safe({'at': stamp(), **data}))
        return path

    def end(self, path, data): write_new(path.with_suffix('.end.json'), safe({'at': stamp(), **data}))


class BoundedProvider:
    name='supervised-deepseek-paired-agent'
    live=True

    def __init__(self, client, journal, expected_messages, expected_model=None):
        self.client, self.journal = client, journal
        self.expected_messages, self.expected_model = expected_messages, expected_model
        self.calls=[]

    def generate(self, messages):
        if len(self.calls) >= SERVICE['max_requests_per_arm']: raise AgentTransportError('request_budget_exhausted')
        if len(json.dumps(messages, ensure_ascii=False)) > SERVICE['max_context_chars_per_request']:
            raise AgentTransportError('context_budget_exhausted')
        if not self.calls and messages != self.expected_messages: raise AgentTransportError('initial_input_mismatch')
        body=payload(messages)
        if len(json.dumps(body, ensure_ascii=False).encode()) > SERVICE['max_request_bytes']:
            raise AgentTransportError('request_byte_budget_exhausted')
        if safe(body) != body: raise AgentTransportError('sensitive_outbound_blocked')
        path=self.journal.start('requests', {'payload': body, 'endpoint': SERVICE['endpoint']})
        record={'request_number':len(self.calls)+1, 'resolved_model':None, 'system_fingerprint':None,
                'usage':usage_record(None), 'error_type':None, 'request_payload_sha256':hashlib.sha256(encode(body)).hexdigest()}
        self.calls.append(record)
        started=perf_counter()
        try:
            try: response=self.client._post('/chat/completions',body)
            except Exception: raise AgentTransportError('transport_failed_no_retry') from None
            record.update(resolved_model=response.get('model'), system_fingerprint=response.get('system_fingerprint'),
                          usage=usage_record(response.get('usage')), response_id=response.get('id'))
            choice=response.get('choices',[{}])[0]
            record.update(finish_reason=choice.get('finish_reason'), raw_response=choice.get('message',{}).get('content'))
            model=record['resolved_model']
            if not isinstance(model,str) or not model or (self.expected_model and model != self.expected_model):
                raise AgentTransportError('returned_model_missing_or_changed')
            self.expected_model=model
            if record['usage']['output_tokens'] is not None and record['usage']['output_tokens'] > SERVICE['max_completion_tokens']:
                raise AgentTransportError('service_output_budget_violated')
            if record['finish_reason'] != 'stop' or not isinstance(record['raw_response'], str):
                raise AgentTransportError('incomplete_response_no_retry')
            try: return ActionBatch.model_validate(_json_loads(record['raw_response']))
            except Exception: raise AgentTransportError('invalid_actions_no_retry') from None
        except BaseException as exc:
            record['error_type']=safe_text(exc,120) if isinstance(exc,AgentTransportError) else type(exc).__name__
            if isinstance(exc, Exception) and not isinstance(exc, AgentTransportError):
                raise AgentTransportError('invalid_response_no_retry') from None
            raise
        finally:
            record['elapsed_seconds']=perf_counter()-started
            self.journal.end(path,record)

    def safe_metadata(self): return {'name':self.name,'live':True,'request_count':len(self.calls)}


class LoggedWorkspace:
    def __init__(self, workspace, journal): self.workspace,self.journal=workspace,journal
    def __getattr__(self, name):
        target=getattr(self.workspace,name)
        if name not in {'list_files','read_file','write_file','git_diff','protected_integrity','changed_files'}: return target
        def invoke(*args, **kwargs):
            path=self.journal.start('tools',{'tool':name,'arguments':list(args),'keywords':kwargs})
            try:
                result=target(*args,**kwargs)
                self.journal.end(path,{'tool':name,'status':'ok','result':result})
                return result
            except BaseException as exc:
                self.journal.end(path,{'tool':name,'status':'error','error_type':type(exc).__name__})
                raise
        return invoke


class LoggedSandbox(DockerSandbox):
    def __init__(self,image,config_dir,journal): super().__init__(image,config_dir);self.journal=journal
    def run_args(self,repo,*,judge_dir=None,name,owner):
        write_new(self.journal.root/'containers'/(owner+'.json'),{'name':name,'owner':owner})
        return super().run_args(repo,judge_dir=judge_dir,name=name,owner=owner)
    def run_tests(self,*args,**kwargs):
        path=self.journal.start('tests',{'expected_count':kwargs['expected_count'],'independent_judge':kwargs.get('judge_dir') is not None})
        result=super().run_tests(*args,**kwargs)
        self.journal.end(path,result)
        return result


def live_config():
    from repomind.intelligence.config import load_env_file
    load_env_file()
    key=os.environ.get('DEEPSEEK_API_KEY') or os.environ.get('REPOMIND_API_KEY')
    if not key: raise ValueError('需要本机 DEEPSEEK_API_KEY；不在报告中保存凭据。')
    return ProviderConfig(base_url='https://api.deepseek.com',api_key=key,chat_model=SERVICE['model'],api_style='deepseek',
                          timeout_seconds=SERVICE['request_timeout_seconds'],max_completion_tokens=2048,
                          max_request_bytes=SERVICE['max_request_bytes'],max_response_bytes=SERVICE['max_response_bytes'])


class SimulationClient:
    """Explicit diagnostic only. No HTTP client, actual usage or model claims."""
    def __init__(self,suite):
        self.responses=read_json(Path(suite)/'offline-actions.jsonl')['responses'];self.index=0
    def _post(self,suffix,body):
        response=self.responses[self.index];self.index+=1
        return {'model':'simulation-no-model','choices':[{'finish_reason':'stop','message':{'content':json.dumps(response,ensure_ascii=False)}}]}


def execute_arm(suite,directory,config_dir,name,expected_model=None,*,client=None,sandbox=None,simulation=False):
    suite,protocol,task=load_live(suite)
    directory=Path(directory);journal=Journal(directory);started=perf_counter()
    facts=[] if name==ARMS[0] else json.loads((suite/'memory.json').read_text(encoding='utf-8'))
    review=json.loads((suite/'outbound-review.json').read_text(encoding='utf-8'))['arms'][name]
    workspace=TaskWorkspace(directory/'repo',task,suite)
    write_new(directory/'input.json',{'messages':review['messages']})
    before={p:digest(workspace.root/p) for p in workspace.allowed}
    write_new(directory/'initial.json',{'hashes':before,'name':name,'memory_input':facts})
    provider=BoundedProvider(client or (SimulationClient(suite) if simulation else OpenAICompatibleProvider(live_config())),journal,review['messages'],expected_model)
    sandbox=sandbox or LoggedSandbox(protocol['image'],config_dir,journal)
    result=run_agent(task,LoggedWorkspace(workspace,journal),provider,sandbox,{'facts':facts},budget=AgentBudget(**protocol['budget']))
    write_new(directory/'agent.json',safe(result))
    # Grading is never sent to the provider; there are no more model calls below.
    public=sandbox.run_tests(workspace.root,expected_count=task.public_count)
    judge=directory/'judge';judge.mkdir();(judge/'test_acceptance.py').write_bytes((suite/task.acceptance_test).read_bytes())
    acceptance=sandbox.run_tests(workspace.root,expected_count=task.acceptance_count,judge_dir=judge)
    intact=workspace.protected_integrity()
    infrastructure=result['status'] in {'model_transport_error','sandbox_error'} or any(g['infrastructure_error'] or g.get('execution_error') or not g['test_report'] for g in (public,acceptance))
    arm={'name':name,'memory_input':facts,'memory_bytes':len(json.dumps({'facts':facts},ensure_ascii=False).encode()),
         'status':result['status'],'initial_code_hashes':before,'final_public':public,'acceptance':acceptance,
         'checks_passed':sum(g['test_report']['passed'] if g['test_report'] else 0 for g in (public,acceptance)),
         'checks_total':task.public_count+task.acceptance_count,'protected_files_intact':intact,
         'strict_success':int(result['status']=='finished' and bool(result['changed_files']) and public['passed'] and acceptance['passed'] and intact and not infrastructure),
         'infrastructure_error':bool(infrastructure),'elapsed_seconds':perf_counter()-started,'agent_elapsed_seconds':result['elapsed_seconds'],
         'money':None,'claim':{'speaker':'model','text':result['summary'],'is_model_claim':True},
         'observed':{'source_reads':[o['arguments']['path'] for o in result['observations'] if o['tool']=='read_file'],
                     'changed_files':result['changed_files'],'causal_memory_use':'自述、读写和测试不能证明模型内部使用了记忆。'},
         'commands':[{'tool':o['tool'],'path':o.get('arguments',{}).get('path'),'status':o['status'],
                      'exit_code':(o.get('result') or {}).get('exit_code'),'output':safe_text((o.get('result') or {}).get('stdout',''))} for o in result['observations']],
         'diff':result['diff']}
    arm.update(usage_summary(directory))
    if simulation:
        arm.update(simulated_requests=arm['model_requests'],model_requests=0,
                   claim={'speaker':'scripted_fixture','text':result['summary'],'is_model_claim':False})
    write_new(directory/'result.json',safe(arm))
    return arm


def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def usage_summary(directory):
    starts=sorted((Path(directory)/'requests').glob('*.start.json'))
    records=[]
    for path in starts:
        end=path.with_name(path.name.replace('.start.json','.end.json'))
        try: record=read_json(end)
        except (OSError,ValueError): record={'usage':usage_record(None),'error_type':'request_interrupted_usage_unknown'}
        records.append(record)
    complete=bool(records) and all(r['usage']['complete'] for r in records)
    def total(key):
        values=[r['usage'][key] for r in records]
        return sum(values) if complete and all(v is not None for v in values) else None
    return {'model_requests':len(starts),'usage_complete':complete,'input_tokens':total('input_tokens'),
            'output_tokens':total('output_tokens'),'total_tokens':total('total_tokens'),'cached_input_tokens':total('cached_input_tokens'),
            'resolved_models':sorted({r['resolved_model'] for r in records if isinstance(r.get('resolved_model'),str)}),
            'system_fingerprints':sorted({r['system_fingerprint'] for r in records if isinstance(r.get('system_fingerprint'),str)}),
            'request_records':records}


def supervise(args,directory,seconds):
    """Hard wall limit for the owned arm process, including HTTP, tools and grading."""
    started=perf_counter()
    with (Path(directory)/'worker.log').open('xb') as log:
        process=subprocess.Popen(args,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        write_new(Path(directory)/'worker-start.json',{'pid':process.pid,'at':stamp(),'wall_limit_seconds':seconds})
        try:
            process.wait(timeout=max(0,seconds-(perf_counter()-started)))
            status='exited' if process.returncode==0 else 'worker_failed'
        except subprocess.TimeoutExpired:
            status='time_limit'
        except BaseException:
            status='interrupted'
            raise
        finally:
            if process.poll() is None:
                process.kill();process.wait(timeout=5)
            write_new(Path(directory)/'worker-end.json',{'status':status,'exit_code':process.returncode,'elapsed_seconds':perf_counter()-started,'at':stamp()})
    return status


def cleanup(directory,sandbox):
    result=[]
    for file in sorted((Path(directory)/'containers').glob('*.json')):
        row=read_json(file)
        result.append({'name':row['name'],'verified':sandbox._cleanup(row['name'],row['owner'])})
    return result


def partial_arm(directory,name,facts,status,elapsed):
    initial=Path(directory)/'initial.json'
    evidence=[]
    for path in sorted((Path(directory)/'tools').glob('*.start.json')):
        end=path.with_name(path.name.replace('.start.json','.end.json'))
        try: item=read_json(path)
        except (OSError,ValueError): item={'tool':'unknown','status':'partial_record'}
        try: item.update(read_json(end))
        except (OSError,ValueError): item['status']='interrupted'
        evidence.append(item)
    agent_path=Path(directory)/'agent.json'
    agent=read_json(agent_path) if agent_path.exists() else {}
    reads=[e['arguments'][0] for e in evidence if e['tool']=='read_file' and e.get('status')=='ok']
    return {'name':name,'status':status,'memory_input':facts,'memory_bytes':len(json.dumps({'facts':facts},ensure_ascii=False).encode()),
            'initial_code_hashes':read_json(initial)['hashes'] if initial.exists() else {},
            'final_public':None,'acceptance':None,'checks_passed':0,'checks_total':27,'strict_success':0,
            'infrastructure_error':True,'elapsed_seconds':elapsed,'agent_elapsed_seconds':elapsed,'money':None,
            'claim':{'speaker':'model','text':agent.get('summary'),'is_model_claim':True},
            'observed':{'source_reads':reads,'changed_files':agent.get('changed_files',[]),'causal_memory_use':'运行中断；请核对已保存请求及工具片段。'},
            'commands':evidence,'diff':agent.get('diff',''),'evidence_incomplete':True,**usage_summary(directory)}


def finish_report(report):
    arms=report['arms']
    if report.get('kind')=='protocol_simulation':
        for a in arms:
            a.update(simulated_requests=a.get('simulated_requests',a['model_requests']),model_requests=0)
    report['new_model_requests']=sum(a['model_requests'] for a in arms)
    report['actual_tokens']=sum(a['total_tokens'] for a in arms) if len(arms)==2 and all(a['total_tokens'] is not None for a in arms) else None
    models={m for a in arms for m in a['resolved_models']}
    fingerprints={m for a in arms for m in a['system_fingerprints']}
    report['comparability']={'model_identifiers':sorted(models),'system_fingerprints':sorted(fingerprints),
                             'returned_models_match':len(models)==1 and len(arms)==2 and all(a['resolved_models'] for a in arms),
                             'fingerprints_match_when_reported':len(fingerprints)<=1}
    comparable=report['status']=='completed' and report.get('initial_files_identical') and report['comparability']['returned_models_match'] and len(fingerprints)<=1
    report['verdict']=effect_verdict(arms,real=True,comparable=bool(comparable))
    if report.get('kind')=='protocol_simulation':
        report['verdict']={'direction':'not_measured','reason':'模拟响应和真实容器只验证执行链路；没有真实模型效果或 Token。'}
    report['quality_observation']=[{'arm':a['name'],'strict_success':a['strict_success'],'checks_passed':a['checks_passed'],
                                   'verified':not a.get('evidence_incomplete',False)} for a in arms]
    return report


def run_live(suite,run_dir,config_dir,approved_review_sha256,*,supervisor=supervise,sandbox=None,check_config=True,simulation=False):
    suite,protocol,task=load_live(suite)
    if approved_review_sha256 != digest(suite/'outbound-review.json'):
        raise ValueError('必须明确批准当前确切发送清单 SHA-256；尚未调用模型。')
    if check_config and not simulation: live_config()  # Local only. Never uses a configured alternate endpoint/model.
    run_dir=Path(run_dir).resolve()
    if run_dir.exists(): raise ValueError('运行目录必须是新目录，首次结果不覆盖。')
    run_dir.mkdir(parents=True)
    report={'stage_goal':GOAL,'id':'pair-'+uuid4().hex[:12],'project':task.project_id,'kind':'protocol_simulation' if simulation else 'live_model',
            'status':'running','frozen':protocol,'manifest_sha256':digest(suite/'manifest.json'),
            'approved_review_sha256':approved_review_sha256,'arms':[],'new_model_requests':0,'actual_tokens':None,
            'actual_cost':None,'started_at':stamp(),'verdict':{'direction':'inconclusive','reason':'真实运行尚未完成。'}}
    write_new(run_dir/'first-start.json',report)
    snapshot(run_dir/'report.json',report)
    sandbox=sandbox or DockerSandbox(protocol['image'],config_dir)
    active=None
    try:
        report['sandbox']=sandbox.probe()
        for index,name in enumerate(ARMS):
            directory=run_dir/('a' if index==0 else 'b');directory.mkdir();clock=perf_counter()
            facts=[] if index==0 else read_json(suite/'memory.json')
            active=(directory,name,facts,clock)
            expected=(report['arms'][0]['resolved_models'][0] if index else '')
            args=[sys.executable,'-m','repomind.memory_effect_live','worker',str(suite),str(directory),str(Path(config_dir).resolve()),name,expected,
                  'simulation' if simulation else 'live']
            state=supervisor(args,directory,SERVICE['wall_seconds_per_arm'])
            result=directory/'result.json'
            if state=='exited' and result.exists(): arm=read_json(result)
            else: arm=partial_arm(directory,name,facts,state,perf_counter()-clock)
            arm['supervision_status']=state
            arm['elapsed_seconds']=perf_counter()-clock
            arm['cleanup']=cleanup(directory,sandbox)
            if not all(r['verified'] for r in arm['cleanup']): arm['infrastructure_error']=True
            report['arms'].append(arm);active=None
            snapshot(run_dir/'report.json',finish_report(report))
            if arm['infrastructure_error']: raise ValueError('运行异常，保留首次证据并停止；不自动重试。')
        report['initial_files_identical']=report['arms'][0]['initial_code_hashes']==report['arms'][1]['initial_code_hashes']
        report['status']='completed'
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',error=type(exc).__name__)
        if active:
            directory,name,facts,clock=active
            arm=partial_arm(directory,name,facts,'interrupted',perf_counter()-clock)
            arm['cleanup']=cleanup(directory,sandbox);report['arms'].append(arm)
    report['ended_at']=stamp()
    finish_report(report)
    write_new(run_dir/'final-report.json',report)
    snapshot(run_dir/'report.json',report)
    return report


def recover(run_dir,config_dir,*,worker_stopped=False):
    """Finalize a coordinator killed externally. Never start a model or retry."""
    run_dir=Path(run_dir).resolve()
    if (run_dir/'final-report.json').exists(): raise ValueError('已有最终回执，不覆盖。')
    report=read_json(run_dir/'first-start.json')
    sandbox=DockerSandbox(report['frozen']['image'],config_dir)
    report.update(status='interrupted',error='coordinator_interrupted',arms=[],ended_at=stamp())
    for index,name in enumerate(ARMS):
        directory=run_dir/('a' if index==0 else 'b')
        if not directory.exists(): continue
        if (directory/'worker-start.json').exists() and not (directory/'worker-end.json').exists() and not worker_stopped:
            raise ValueError('先核对并停止该运行自己的 worker；不能把仍在执行的请求当作已停止。')
        initial=directory/'initial.json';facts=read_json(initial)['memory_input'] if initial.exists() else []
        arm=read_json(directory/'result.json') if (directory/'result.json').exists() else partial_arm(directory,name,facts,'interrupted',0)
        arm['cleanup']=cleanup(directory,sandbox);report['arms'].append(arm)
    finish_report(report);write_new(run_dir/'final-report.json',report);snapshot(run_dir/'report.json',report)
    return report


if __name__=='__main__':
    if len(sys.argv)!=8 or sys.argv[1]!='worker' or sys.argv[7] not in {'simulation','live'}: raise SystemExit('Internal supervised worker only.')
    directory=Path(sys.argv[3])
    # Independent fail-safe if the coordinating process itself is killed.
    import threading
    def watchdog_stop():
        write_new(directory/'watchdog-stop.json',{'at':stamp(),'reason':'arm_wall_limit'})
        os._exit(124)
    watchdog=threading.Timer(SERVICE['wall_seconds_per_arm'],watchdog_stop)
    watchdog.daemon=True;watchdog.start()
    try:
        execute_arm(sys.argv[2],directory,sys.argv[4],sys.argv[5],sys.argv[6] or None,simulation=sys.argv[7]=='simulation')
    except BaseException as exc:
        write_new(directory/'worker-error.json',{'error_type':type(exc).__name__,'at':stamp()})
        raise SystemExit(2)
    finally:
        watchdog.cancel()
