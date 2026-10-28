"""Owned fixture trials, independent grading, and precomputed trace export."""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import re
from time import perf_counter
from uuid import uuid4

from repomind import __version__
from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.agent.loop import run_agent
from repomind.agent.memory import ExperienceStore,MemoryScopeViolation,VARIANTS,memory_context
from repomind.agent.models import AgentBudget,AgentTask
from repomind.agent.providers import LiveAgentProvider,ReplayAgentProvider,PROMPT_SHA256
from repomind.agent.sandbox import DockerSandbox
from repomind.agent.workspace import TaskWorkspace,ToolDenied,checked_path,digest
from repomind.comparison.pricing import estimate_cost,load_price_card
from repomind.evaluation.intelligent import _implementation_hash
from repomind.memory.store import _unique_keys
from repomind.platform.tracing import TraceOutbox,TraceRecord,clean_payload

GOAL='V2.0：用隔离代码工具完成样例任务，测量当前记忆与时序/经验增强的实际作用'


def verified_manifest(data_root):
    root=Path(data_root).resolve()
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'),object_pairs_hook=_unique_keys)
    if manifest.get('synthetic') is not True or manifest.get('dataset_version')!='2.0.0':
        raise ValueError('developer benchmark requires the explicitly synthetic frozen V2 dataset')
    for relative,entry in manifest['files'].items():
        if digest(checked_path(root,relative))!=entry['sha256']:
            raise ValueError('V2 input differs from its frozen manifest')
    return manifest


def load_tasks(path):
    rows=[AgentTask.model_validate(json.loads(line,object_pairs_hook=_unique_keys)) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    if not rows or len(rows)>12 or len({r.task_id for r in rows})!=len(rows):
        raise ValueError('developer dataset must contain 1..12 uniquely identified tasks')
    if any(not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',r.task_id) for r in rows):
        raise ValueError('task IDs must be bounded directory-safe labels')
    return rows


def _provider(mode,root,task):
    return LiveAgentProvider() if mode=='live' else ReplayAgentProvider(root/'recorded-actions.jsonl',task.task_id)


def _model_observations(provider,card,run_date):
    rows=[]
    for number,call in enumerate(provider.calls,1):
        pricing=estimate_cost(call['usage'],call['model'],card,live=True,run_date=run_date,
                              operation='chat',usage_complete=call['usage_complete'])
        row={'name':'agent_model_turn_'+str(number),'as_type':'generation','model':call['model'],
             'input':call['input'],'output':call['raw_response'],'elapsed_seconds':call['elapsed_seconds'],
             'usage_details':call['usage'] if call['usage_complete'] else None,
             'metadata':{'original_started_at':call['started_at'],'original_ended_at':call['ended_at'],
                         'observed_usage':call['usage'],'usage_complete':call['usage_complete'],
                         'pricing_result':pricing,'error_type':call['error_type'],'resolved_model':call.get('resolved_model')}}
        if pricing['amount'] is not None and pricing['currency']=='USD':
            row['cost_details']={'total':pricing['amount']}
        rows.append(row)
    return rows


def _aggregate(trials):
    usage=Counter()
    for row in trials:
        usage.update(row.get('agent',{}).get('model',{}).get('usage',{}))
    return {'total_tasks':len(trials),'successful_tasks':sum(row['task_success'] for row in trials),
            'task_success_rate':sum(row['task_success'] for row in trials)/len(trials),
            'tasks_with_retry':sum(row.get('agent',{}).get('retry_count',0)>0 for row in trials),
            'retry_rate':sum(row.get('agent',{}).get('retry_count',0)>0 for row in trials)/len(trials),
            'public_test_failures':sum(row.get('agent',{}).get('public_test_failures',0) for row in trials),
            'blocked_actions':sum(row.get('agent',{}).get('blocked_actions',0) for row in trials),
            'model_requests':sum(row.get('agent',{}).get('model',{}).get('request_count',0) for row in trials),
            'usage':dict(usage),'infrastructure_errors':sum(bool(row['infrastructure_error']) for row in trials),
            'memory_scope_violations':sum(row.get('memory_scope_violation',False) for row in trials)}


def render(report):
    lines=['# 阶段目标：'+GOAL,'',f"运行 `{report['run_id']}`；模式 `{report['config']['provider_mode']}`。",'',
           '| 方案 | 任务成功 | 重试率 | 实际模型请求 | 输入token | 输出token | 工程错误 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for name,arm in report['variants'].items():
        m=arm['metrics']; u=m['usage']
        lines.append(f"| {name} | {m['successful_tasks']}/{m['total_tasks']} | {m['retry_rate']:.1%} | {m['model_requests']} | {u.get('prompt_tokens','N/A')} | {u.get('completion_tokens','N/A')} | {m['infrastructure_errors']} |")
    lines+=['','## 解释范围','','- replay对三组使用同一人工参考补丁，仅验工程管线，不测模型质量或记忆收益。',
            '- baseline无记忆；memory读取当前事实；enhanced使用任务双时间并读取同run、同项目的此前成功经验。两项增强绑在一起，不能分别归因。',
            '- 公开测试供Agent修复；隐藏测试在Agent停止后才执行，结果不反馈给该任务模型；保护不等于抵御故意伪造判题。',
            '- 任务是合成业务代码样例，作者与实现者同会话；不是生产仓库/SWE-bench或独立盲测。样本少，不预设记忆必胜。',
            '- Docker隔离宿主能力；镜像/路径/资源配置和实际测试另见JSON，不声称防御内核漏洞。',
            '- Token只取实际响应，价卡缺失时货币费用未知；Langfuse只回放既有结果。','',
            '## 失败任务','','```json',json.dumps(report['failures'],ensure_ascii=False,indent=2),'```','',
            '## 配置','','```json',json.dumps(report['config'],ensure_ascii=False,indent=2),'```','']
    return '\n'.join(lines)


def run_developer_benchmark(dataset_path,output_path,*,image,config_dir,data_root='data/v2',provider_mode='replay',
                            variants=None,state_dir='work/v2-runs',run_id=None,seed=0,budget=None,pricing_path=None):
    started=perf_counter()
    root=Path(data_root).resolve()
    dataset=Path(dataset_path).resolve()
    output=Path(output_path)
    if provider_mode not in {'live','replay'} or output.suffix not in {'.md','.json'}:
        raise ValueError('expected live/replay mode and .json/.md report output')
    manifest=verified_manifest(root)
    try:
        relative=dataset.relative_to(root).as_posix()
    except ValueError:
        raise ValueError('tasks must belong to the frozen V2 benchmark') from None
    if relative not in manifest['files']:
        raise ValueError('dataset is not a frozen benchmark input')
    tasks=load_tasks(dataset)
    names=list(VARIANTS if variants is None else variants)
    if not names or len(names)!=len(set(names)) or any(n not in VARIANTS for n in names):
        raise ValueError('variants must be unique baseline/memory/enhanced choices')
    run_id=run_id or 'v2-'+uuid4().hex
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}',run_id) or type(seed) is not int:
        raise ValueError('run_id/seed are invalid')
    directory=Path(state_dir).absolute()/run_id
    if directory.resolve().is_relative_to(root):
        raise ValueError('runtime state must not be written inside frozen benchmark inputs')
    outbox_path=output.with_suffix('.traces.jsonl')
    targets=[output.with_suffix('.json'),output.with_suffix('.md'),outbox_path,Path(str(outbox_path)+'.status.jsonl')]
    if any(p.exists() or p.resolve().is_relative_to(root) or p.resolve().is_relative_to(directory) for p in targets) or directory.exists():
        raise ValueError('preserve existing reports/run inputs; choose fresh external report paths and run_id')
    budget=budget or AgentBudget()
    card,card_hash=load_price_card(pricing_path) if pricing_path else (None,None)
    sandbox=DockerSandbox(image,config_dir)
    sandbox_metadata=sandbox.probe() # fail closed before reading API credentials/calling models
    directory.mkdir(parents=True,exist_ok=False)
    order=list(names); random.Random(seed).shuffle(order)
    outbox=TraceOutbox(outbox_path)
    variants_report={}
    failures=[]
    run_date=datetime.now(timezone.utc).date()
    for variant in order:
        arm_dir=directory/variant
        arm_dir.mkdir()
        experience=ExperienceStore(arm_dir/'experiences.sqlite3')
        trials=[]
        try:
            with SQLiteMemoryStore(arm_dir/'ledger.sqlite3') as ledger:
                ledger.import_jsonl(root/'events.jsonl')
                for sequence,task in enumerate(tasks):
                    clock=perf_counter()
                    trial_dir=arm_dir/task.task_id
                    trial_dir.mkdir()
                    provider=None
                    agent={}
                    context=None
                    error=None
                    scope_violation=False
                    public=hidden=None
                    experience_id=None
                    try:
                        workspace=TaskWorkspace(trial_dir/'repo',task,root)
                        context=memory_context(task,variant,ledger,experience,sequence=sequence,current_as_of=manifest['current_memory_as_of'])
                        provider=_provider(provider_mode,root,task)
                        agent=run_agent(task,workspace,provider,sandbox,context,budget=budget)
                        if agent['status'] not in {'sandbox_error','model_transport_error'}:
                            public=sandbox.run_tests(workspace.root,expected_count=task.public_count)
                            if not public['infrastructure_error']:
                                judge=trial_dir/'judge'
                                judge.mkdir()
                                (judge/'test_acceptance.py').write_bytes(checked_path(root,task.acceptance_test).read_bytes())
                                hidden=sandbox.run_tests(workspace.root,expected_count=task.acceptance_count,judge_dir=judge)
                        workspace.protected_integrity()
                    except Exception as exc:
                        error=type(exc).__name__
                        scope_violation=isinstance(exc,MemoryScopeViolation)
                    infrastructure=bool(error or agent.get('status') in {'sandbox_error','model_transport_error'}
                        or any(o['status']=='error' and o['tool']!='model' for o in agent.get('observations',[]))
                        or (public and public['infrastructure_error']) or (hidden and hidden['infrastructure_error']))
                    success=bool(not infrastructure and agent.get('status')=='finished' and agent.get('changed_files')
                                 and public and public['passed'] and hidden and hidden['passed'])
                    if success and variant=='enhanced':
                        experience_id=experience.add(project_id=task.project_id,category=task.category,task_id=task.task_id,
                            summary=agent['summary'],source_run=run_id,sequence=sequence)
                    if provider is not None and 'model' not in agent:
                        agent['model']=provider.safe_metadata()
                    row={'task_id':task.task_id,'project_id':task.project_id,'category':task.category,'task_success':success,
                         'infrastructure_error':infrastructure,'error_type':error,'memory_scope_violation':scope_violation,
                         'context':context,'agent':agent,'public_grading':public,'hidden_grading':hidden,
                         'experience_written':experience_id,'elapsed_seconds':perf_counter()-clock,
                         'hidden_grading_fed_back_to_model':False}
                    trials.append(row)
                    if not success:
                        failures.append({'variant':variant,'task_id':task.task_id,'agent_status':agent.get('status'),
                                         'error_type':error,'infrastructure_error':infrastructure,
                                         'public_passed':bool(public and public['passed']),'hidden_passed':bool(hidden and hidden['passed'])})
                    observations=[{'name':'memory_lookup','input':{'mode':variant},'output':context}]
                    if provider is not None:
                        observations+=_model_observations(provider,card,run_date)
                    observations += [{'name':'tool_'+str(i)+'_'+step['tool'],'input':step.get('arguments'),
                                      'output':step.get('result'),'elapsed_seconds':step.get('elapsed_seconds'),
                                      'metadata':{'status':step['status']}} for i,step in enumerate(agent.get('observations',[]))]
                    for name,graded in [('final_public_grading',public),('final_hidden_grading',hidden)]:
                        if graded:
                            observations.append({'name':name,'elapsed_seconds':graded['elapsed_seconds'],
                                                 'output':{'passed':graded['passed'],'test_report':graded['test_report']}})
                    outbox.append(TraceRecord(run_id=run_id,item_id=task.task_id,provider=variant,project_id=task.project_id,
                        stage='developer_task',synthetic=True,
                        input={'task_id':task.task_id,'project_id':task.project_id,'prompt':task.prompt,
                               'as_of':task.as_of.isoformat(),'known_at':task.known_at.isoformat() if task.known_at else None,
                               'writable_paths':task.writable_paths},
                        expected_output={'public_test_count':task.public_count,'acceptance_test_count':task.acceptance_count,'required_agent_status':'finished'},
                        output={'task_success':success,'agent_status':agent.get('status'),'changed_files':agent.get('changed_files',[]),
                                'diff':agent.get('diff'),'public_passed':bool(public and public['passed']),
                                'hidden_passed':bool(hidden and hidden['passed']),'error_type':error},
                        scores={'task_success':float(success),'public_passed':float(bool(public and public['passed'])),
                                'hidden_passed':float(bool(hidden and hidden['passed'])),
                                'retry_count':float(agent.get('retry_count',0)),'scope_violation':float(scope_violation)},
                        observations=observations,
                        metadata={'provider_mode':provider_mode,'validation_kind':'real_model_synthetic_code_tasks' if provider_mode=='live' else 'scripted_solution_not_model_quality',
                                  'sandbox':sandbox_metadata,'memory_mode':variant,'experience_ids_read':[r['experience_id'] for r in (context or {}).get('experiences',[])],
                                  'expected_tests_are_not_model_context':True,'memory_scope_violation':scope_violation}))
        finally:
            experience.close()
        metrics=_aggregate(trials)
        model=(trials[0].get('agent',{}).get('model') or {}).get('chat_model')
        complete=all((row.get('agent',{}).get('model') or {}).get('usage_complete',False) for row in trials)
        variants_report[variant]={'metrics':metrics,'trials':trials,
            'pricing':estimate_cost(metrics['usage'],model,card,live=provider_mode=='live',run_date=run_date,operation='chat',usage_complete=complete)}
    report={'stage_goal':GOAL,'version':__version__,'run_id':run_id,'created_at':datetime.now(timezone.utc).isoformat(),
            'config':{'provider_mode':provider_mode,'dataset':str(dataset),'dataset_sha256':digest(dataset),
                      'manifest_sha256':digest(root/'manifest.json'),'implementation_sha256':_implementation_hash(),
                      'prompt_sha256':PROMPT_SHA256,'task_ids':[t.task_id for t in tasks],'budget':budget.model_dump(),
                      'seed':seed,'provider_order':order,'sandbox':sandbox_metadata,'price_card_sha256':card_hash,
                      'experience_policy':'earlier successful tasks in same project and same run only; same-category preferred, latest project fallback; no cross-split history',
                      'primary_comparison':'baseline vs memory vs combined temporal/experience enhanced; same initial code and tool budget'},
            'variants':variants_report,'failures':failures,'outbox':str(outbox_path.resolve()),
            'elapsed_seconds_before_report':perf_counter()-started,
            'validation':{'completed_without_errors':all(a['metrics']['infrastructure_errors']==a['metrics']['memory_scope_violations']==0 for a in variants_report.values()),
                          'cloud_verified':False,'real_model':provider_mode=='live','production_effectiveness_proven':False,
                          'scripted_results_are_not_model_accuracy':provider_mode=='replay'}}
    report=clean_payload(report)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    output.with_suffix('.md').write_text(render(report),encoding='utf-8',newline='\n')
    return report
