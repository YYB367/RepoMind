"""Finite action loop. Hidden grading happens afterwards and never feeds back."""
import json
from time import perf_counter
from pydantic import ValidationError
from repomind.agent.models import AgentBudget
from repomind.agent.providers import SYSTEM_PROMPT,AgentTransportError
from repomind.agent.workspace import ToolDenied


def run_agent(task,workspace,provider,sandbox,context,*,budget=None):
    budget=budget or AgentBudget()
    initial={'task_id':task.task_id,'project_id':task.project_id,'task':task.prompt,
             'as_of':task.as_of.isoformat(),'known_at':task.known_at.isoformat() if task.known_at else None,
             'files':workspace.list_files(),'memory':context,
             'budgets':budget.model_dump()}
    messages=[{'role':'system','content':SYSTEM_PROMPT},{'role':'user','content':json.dumps(initial,ensure_ascii=False)}]
    observations=[]
    turns=actions=test_runs=public_failures=blocked=0
    status='turn_budget_exhausted'
    summary=None
    error_type=None
    started=perf_counter()
    for turn in range(budget.max_turns):
        if len(json.dumps(messages,ensure_ascii=False))>budget.max_context_chars:
            status='context_budget_exhausted'
            break
        turns+=1
        try:
            batch=provider.generate(messages)
        except Exception as exc:
            # Schema/JSON failures are explicit bounded feedback; HTTP errors
            # also consume a turn and are retained by the provider telemetry.
            error_type=type(exc).__name__
            issues=([{'location':list(e['loc']),'type':e['type'],'message':e['msg']} for e in exc.errors(include_input=False,include_url=False)[:6]]
                    if isinstance(exc,ValidationError) else [])
            messages.append({'role':'user','content':json.dumps({'protocol_error':error_type,'issues':issues,'request':'Return a valid JSON actions object using only the declared schema; finish must be alone.'})})
            observations.append({'tool':'model','status':'error','error_type':error_type})
            if isinstance(exc,AgentTransportError):
                status='model_transport_error'
                break
            continue
        messages.append({'role':'assistant','content':batch.model_dump_json()})
        outputs=[]
        finished=False
        for action in batch.actions:
            if actions>=budget.max_actions:
                status='action_budget_exhausted'
                finished=True
                break
            actions+=1
            clock=perf_counter()
            result=None
            record={'tool':action.tool,'arguments':action.model_dump(exclude={'tool'})}
            try:
                if action.tool=='finish':
                    workspace.protected_integrity()
                    summary=action.summary
                    status='finished'
                    finished=True
                    result={'finished':True,'hidden_tests_executed':False}
                elif action.tool=='list_files':
                    result=workspace.list_files()
                elif action.tool=='read_file':
                    result=workspace.read_file(action.path,action.start_line,action.max_lines)
                elif action.tool=='write_file':
                    result=workspace.write_file(action.path,action.content)
                elif action.tool=='git_diff':
                    result=workspace.git_diff()
                elif action.tool=='run_tests':
                    if test_runs>=budget.max_test_runs:
                        raise ToolDenied('public test budget exhausted')
                    workspace.protected_integrity()
                    test_runs+=1
                    result=sandbox.run_tests(workspace.root,expected_count=task.public_count)
                    if not result['passed']:
                        public_failures+=1
                    if result['infrastructure_error']:
                        status='sandbox_error'
                        finished=True
                record.update(status='ok',result=result)
            except ToolDenied:
                blocked+=1
                record.update(status='denied',error_type='ToolDenied',result={'error':'action blocked by the task capability boundary'})
            except Exception as exc:
                error_type=type(exc).__name__
                record.update(status='error',error_type=error_type,result={'error':'tool failed; sensitive upstream details omitted'})
            record['elapsed_seconds']=perf_counter()-clock
            observations.append(record)
            outputs.append({'tool':action.tool,'status':record['status'],'result':record.get('result')})
            if finished:
                break
        if finished:
            break
        messages.append({'role':'user','content':json.dumps({'tool_results':outputs},ensure_ascii=False)})
    workspace.protected_integrity()
    return {'status':status,'summary':summary,'turns':turns,'action_count':actions,'test_runs':test_runs,
            'public_test_failures':public_failures,'retry_count':max(0,test_runs-1),'blocked_actions':blocked,
            'last_error_type':error_type,'observations':observations,'elapsed_seconds':perf_counter()-started,
            'changed_files':workspace.changed_files(),'diff':workspace.git_diff()['diff'],'model':provider.safe_metadata()}
