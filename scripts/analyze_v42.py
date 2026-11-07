"""Audit completed first-run evidence and render V4.2 results without model calls."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from repomind.agent.workspace import digest
from repomind.evaluation.intelligent import _implementation_hash
from repomind.harness.experiment import _summarize, choose_challenger, promotion_reason

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'reports/v4.2'


def read(name):
    return json.loads((REPORTS/name).read_text(encoding='utf-8'))


def write(name,value):
    with (REPORTS/name).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')


def total(row):
    return row['input_tokens']+row['output_tokens']


def main():
    dev,hold,lock,freeze=map(read,('live-dev.json','live-holdout.json','live-selection-lock.json','freeze.json'))
    challenger=lock['challenger']
    names=['reference',challenger]
    assert _implementation_hash()==freeze['implementation_sha256']==lock['identity']['implementation_sha256']
    assert digest(ROOT/'data/v4.2/protocol.json')==freeze['protocol_sha256']==lock['identity']['protocol_sha256']
    assert lock['identity']['model_config']==freeze['model_config']
    assert lock['dev_sha256']==digest(REPORTS/'live-dev.json')
    assert hold['selection_lock_sha256']==digest(REPORTS/'live-selection-lock.json')
    assert dev['identity']==hold['identity']==lock['identity']
    assert choose_challenger(dev['metrics'])==challenger
    raw={}
    for split,count in (('dev',9),('holdout',16)):
        raw[split]=[json.loads(line)['trial'] for line in (REPORTS/f'live-{split}-trials.jsonl').read_text(encoding='utf-8').splitlines()]
        assert len(raw[split])==count
        assert _summarize(raw[split],list((dev if split=='dev' else hold)['metrics']))==(dev if split=='dev' else hold)['metrics']
    all_rows=raw['dev']+raw['holdout']
    calls=[call for row in all_rows for call in row['model_calls']]
    assert 0<len(calls)<=freeze['max_live_requests']
    before=datetime.fromisoformat(freeze['frozen_at'])
    assert all(datetime.fromisoformat(call['started_at'])>=before for call in calls)
    assert all(call['usage_complete'] for call in calls)
    context_counts=[]
    failures=[]
    for split,rows in raw.items():
        for row in rows:
            verified=bool(not row['infrastructure_error'] and row['public_grading'] and row['public_grading']['passed']
                          and row['hidden_grading'] and row['hidden_grading']['passed'])
            assert verified==row['code_verified']
            assert bool(verified and row['agent']['changed_files'] and row['agent']['status']=='finished')==row['strict_success']
            assert row['hidden_feedback_to_model'] is False
            initial=json.loads(row['model_calls'][0]['input'][1]['content'])
            fact_count=len(initial['memory']['facts'])
            assert fact_count==(2 if row['policy']=='reference' else 1)
            context_counts.append({'split':split,'task':row['task_id'],'policy':row['policy'],'repeat':row['repeat'],
                                   'initial_fact_count':fact_count})
            if not row['strict_success']:
                failures.append({'split':split,'task_id':row['task_id'],'policy':row['policy'],'repeat':row['repeat'],
                                 'agent_status':row['agent']['status'],'code_verified':row['code_verified'],
                                 'last_error_type':row['agent']['last_error_type'],
                                 'protocol_errors':[call['error_type'] for call in row['model_calls'] if call['error_type']],
                                 'infrastructure_error':row['infrastructure_error'],
                                 'public_grading':row['public_grading'],'hidden_grading':row['hidden_grading']})
    rounds=[]
    for number,metrics in enumerate(hold['repetitions'],1):
        actual=_summarize([row for row in raw['holdout'] if row['repeat']==number],names)
        assert actual==metrics
        reason=promotion_reason(metrics['reference'],metrics[challenger],live=True)
        assert hold['holdout_gate'][number-1]==reason
        rounds.append({'round':number,'metrics':metrics,'token_saving_fraction':1-total(metrics[challenger])/total(metrics['reference']),
                       'gate':reason,'strict_not_lower':metrics[challenger]['strict']>=metrics['reference']['strict'],
                       'code_not_lower':metrics[challenger]['code_verified']>=metrics['reference']['code_verified']})
    eligible={'strict_completion_gain','token_saving_at_equal_or_better_quality'}
    development_gate=promotion_reason(dev['metrics']['reference'],dev['metrics'][challenger],live=True)
    models={call['resolved_model'] for call in calls}
    consistent=len(models)==1 and None not in models
    supported=consistent and development_gate in eligible and len({r['gate'] for r in rounds})==1 and rounds[0]['gate'] in eligible
    assert supported==hold['promotion_supported']
    assert development_gate==hold['development_gate']
    remaining=[]
    if development_gate not in eligible:
        remaining.append('Development comparison did not meet the predeclared improvement gate: '+development_gate+
                         '; total-token saving '+format(1-total(dev['metrics'][challenger])/total(dev['metrics']['reference']),'.4%')+'.')
    for row in rounds:
        if row['gate'] not in eligible: remaining.append('Holdout round '+str(row['round'])+' lacks a qualifying improvement: '+row['gate']+'.')
    if len({row['gate'] for row in rounds})!=1: remaining.append('The two holdout rounds did not reproduce the same kind of improvement.')
    if not consistent: remaining.append('Model identity differs across the comparison.')
    usage=Counter()
    for call in calls: usage.update(call['usage'])
    testsuite=ET.parse(REPORTS/'pytest-platform.xml').getroot().find('testsuite')
    tests={k:int(testsuite.attrib[k]) for k in ('tests','errors','failures','skipped')}
    assert tests=={'tests':499,'errors':0,'failures':0,'skipped':0}
    result={'stage_goal':'V4.2 independently test pilot-nominated strategies and keep reference unless the original gate is met',
            'version':'4.2.0','engineering_acceptance_passed':True,'experiment_completed':True,
            'policy_promotion_supported':supported,'recommended_policy':hold['recommended_policy'],
            'daily_default_policy':'reference','freeze_commit':'71366dc','locked_challenger':challenger,
            'automated_tests':tests|{'real_docker_cases':4,'warnings':1},
            'simulated_verification':{'final_reference_replay_trials':25,'passed':25,
                'first_authoring_draft_trials':9,'first_authoring_draft_failed_reference_trials':3,
                'authoring_bug_preserved':True,'authoring_calls_to_model':0},
            'real_session_verification':{'new_codex_sessions_in_v42':0,'pilot_source_session':'01a1b43d-604d-7ca0-bf23-5f8b9d6c2740'},
            'real_model_experiment':{'development':dev['metrics'],'development_gate':development_gate,
                'rounds':rounds,'actual_requests':len(calls),'max_requests':150,'usage':dict(usage),
                'resolved_models':sorted(models),'model_consistent':consistent,'usage_complete':True,
                'no_hidden_feedback':True,'infrastructure_errors':sum(row['infrastructure_error'] for row in all_rows),
                'monetary_cost':None},
            'failures':[ {key:value for key,value in row.items() if key not in {'public_grading','hidden_grading'}} for row in failures],
            'interpretation':'Controlled, author-constructed RepoMind-derived helper tasks; two rounds reuse the same four new holdout tasks. This is not third-party blind testing or production/Codex effectiveness proof.',
            'remaining_evidence':remaining,
            'stop_after_version':'V4.2'}
    write('context-audit.json',{'stage_goal':'Audit actual model inputs and frozen context scope','rows':context_counts})
    write('failures.json',{'stage_goal':'Retain actual V4.2 trial failures without rerunning or changing the gate','failures':failures})
    write('acceptance.json',result)
    combined=REPORTS/'live-trials.jsonl'
    with combined.open('xb') as stream:
        for split in ('dev','holdout'): stream.write((REPORTS/f'live-{split}-trials.jsonl').read_bytes())
    lines=['# 阶段目标','',result['stage_goal'],'','## 开发集与两轮保留成绩','',
           '| 阶段 | 策略 | 严格完成 | 代码通过 | 请求 | 输入 Token | 输出 Token | 总 Token |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for label,metrics in [('开发',dev['metrics']),*[(f'保留第 {r["round"]} 轮',r['metrics']) for r in rounds]]:
        for name,row in metrics.items():
            lines.append(f'| {label} | {name} | {row["strict"]}/{row["tasks"]} | {row["code_verified"]}/{row["tasks"]} | {row["requests"]} | {row["input_tokens"]:,} | {row["output_tokens"]:,} | {total(row):,} |')
    lines.extend(['','## 门槛判定','',f'锁定候选：{challenger}。开发判定：{development_gate}。'])
    for r in rounds: lines.append(f'- 第 {r["round"]} 轮：{r["gate"]}；总 Token 节省 {r["token_saving_fraction"]:.2%}；严格完成不降={r["strict_not_lower"]}，代码通过不降={r["code_not_lower"]}。')
    lines.extend(['',f'支持晋升：{supported}。实验推荐：{hold["recommended_policy"]}。日常默认仍为 reference。',
                  '',f'实际请求 {len(calls)} 次。输入 {usage["prompt_tokens"]:,}、输出 {usage["completion_tokens"]:,}、合计 {usage["prompt_tokens"]+usage["completion_tokens"]:,} Token。金额未知。',
                  '',f'失败试验 {len(failures)} 项，详见 failures.json；完整首次请求与工具轨迹见 live-trials.jsonl。',
                  '',result['interpretation'],'','网页/新会话的既有验证见 V4.1，本轮没有新增 Codex 会话，也没有把参考动作回放当模型收益。',''])
    with (REPORTS/'results.md').open('x',encoding='utf-8',newline='\n') as stream: stream.write('\n'.join(lines))
    print(json.dumps({'requests':len(calls),'challenger':challenger,'promotion_supported':supported,'round_gates':hold['holdout_gate']}))


if __name__=='__main__': main()
