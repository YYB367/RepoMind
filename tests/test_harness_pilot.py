import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from repomind.agent.workspace import digest
from repomind.harness.experiment import BUDGET, _inputs, choose_challenger, run_phase
from repomind.harness.pilot import PILOT_POLICIES, pilot_receipt, task_context

ROOT=Path(__file__).resolve().parents[1]


def test_real_pilot_nomination_preserves_the_original_evidence():
    path=ROOT/'reports/v4.1/new-session.json'
    receipt=pilot_receipt(path,digest(path))
    assert receipt['recalled_facts']==2 and receipt['unrelated_facts']==1
    assert receipt['candidates']==['reference',*PILOT_POLICIES]
    assert receipt['session_id']=='01a1b43d-604d-7ca0-bf23-5f8b9d6c2740'
    with pytest.raises(ValueError,match='differs'):
        pilot_receipt(path,'0'*64)


def test_focused_context_is_exact_immutable_and_fails_on_cross_project():
    snapshot={'project_id':'RepoMind','facts':[
        {'subject':'codex','field':'path','value':'one','source_id':'s1'},
        {'subject':'harness','field':'path','value':'two','source_id':'s2'}]}
    task=SimpleNamespace(project_id='RepoMind',memory_keys=[('codex','path')])
    focused=task_context(task,snapshot,focused=True)
    assert len(focused['facts'])==1 and focused['facts'][0]['source_id']=='s1'
    focused['facts'][0]['value']='modified'
    assert snapshot['facts'][0]['value']=='one'
    assert len(task_context(task,snapshot,focused=False)['facts'])==2
    task.memory_keys=[]
    assert len(task_context(task,snapshot,focused=True)['facts'])==2
    task.project_id='Other'
    with pytest.raises(ValueError,match='another project'): task_context(task,snapshot,focused=True)


def test_new_suite_and_budgets_are_frozen_and_disjoint_from_v3():
    root=ROOT/'data/v4.2'
    protocol=json.loads((root/'protocol.json').read_text())
    assert protocol['budget']==BUDGET.model_dump() and protocol['max_model_requests']==150
    old=set()
    for suite in ('v3','v3-recovery'):
        for split in ('dev','holdout'):
            old.update(json.loads(line)['task_id'] for line in (ROOT/'data'/suite/split/'tasks.jsonl').read_text().splitlines())
    for split in ('dev','holdout'):
        _,tasks=_inputs(root,split,protocol)
        assert not old & {task.task_id for task in tasks}
        assert all(task.project_id=='RepoMind' and len(task.memory_keys)==1 for task in tasks)
    metrics=lambda strict,tokens:{'strict':strict,'code_verified':3,'input_tokens':tokens,'output_tokens':10,'infrastructure_errors':0}
    assert choose_challenger({'reference':metrics(3,100),'focused-evidence':metrics(2,1),
                             'focused-evidence-compact':metrics(3,200)})=='focused-evidence-compact'


def test_v42_rejects_budget_or_snapshot_changes_before_docker(tmp_path):
    suite=tmp_path/'suite';suite.mkdir()
    protocol=json.loads((ROOT/'data/v4.2/protocol.json').read_text())
    protocol['budget']['max_turns']=7
    (suite/'protocol.json').write_text(json.dumps(protocol))
    with pytest.raises(ValueError,match='budget or scoring'):
        run_phase('tune',suite=suite,history=None,run_dir=tmp_path/'run',image=protocol['image'],config_dir=tmp_path)
    protocol['budget']['max_turns']=6
    (suite/'protocol.json').write_text(json.dumps(protocol))
    (suite/'pilot-memory.json').write_text('{}')
    with pytest.raises(ValueError,match='snapshot differs'):
        run_phase('tune',suite=suite,history=None,run_dir=tmp_path/'run',image=protocol['image'],config_dir=tmp_path)
