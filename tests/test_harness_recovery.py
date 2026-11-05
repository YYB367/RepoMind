import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from repomind.agent.loop import run_agent
from repomind.agent.models import ActionBatch
from repomind.agent.providers import AgentTransportError
from repomind.agent.workspace import digest
from repomind.harness.policy import finish_feedback, recovery_receipt
from repomind.intelligence.providers import _json_loads

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "src/sample.py"


def _workspace():
    return SimpleNamespace(
        root=None,
        list_files=lambda: {"files": [SOURCE]},
        read_file=lambda *args: {"content": "before"},
        write_file=lambda *args: {"path": SOURCE},
        git_diff=lambda: {"diff": "changed"},
        changed_files=lambda: [SOURCE],
        protected_integrity=lambda: None,
    )


def _task():
    return SimpleNamespace(task_id="case", project_id="sample", prompt="Update sample",
                           as_of=datetime(2026, 11, 5, tzinfo=timezone.utc),
                           known_at=None, public_count=2)


@pytest.mark.parametrize("recovery", [False, True])
def test_recovery_keeps_reminder_after_the_two_recorded_failure_types(recovery):
    batches = [
        {"actions": [{"tool": "read_file", "path": SOURCE}]},
        {"actions": [{"tool": "write_file", "path": SOURCE, "content": "after"}]},
        '{"actions":[],"actions":[]}',
        {"actions": [{"tool": "finish", "summary": "done"}, {"tool": "git_diff"}]},
        {"actions": [{"tool": "run_tests"}, {"tool": "git_diff"}]},
        {"actions": [{"tool": "finish", "summary": "done"}]},
    ]
    received = []

    def generate(messages):
        received.append(json.loads(messages[-1]["content"]))
        batch = batches[len(received) - 1]
        return ActionBatch.model_validate(_json_loads(batch) if isinstance(batch, str) else batch)

    provider = SimpleNamespace(generate=generate, safe_metadata=lambda: {})
    sandbox = SimpleNamespace(run_tests=lambda *a, **kw: {"passed": True, "infrastructure_error": False})
    result = run_agent(_task(), _workspace(), provider, sandbox, {}, feedback=finish_feedback,
                       feedback_on_protocol_error=recovery)
    assert received[3]["protocol_error"] == "ValueError"
    assert received[4]["protocol_error"] == "ValidationError"
    assert "controller_note" not in received[3]
    assert ("Two model turns remain" in received[4].get("controller_note", "")) is recovery
    assert "send finish" in received[5]["controller_note"]
    assert result["status"] == "finished" and result["turns"] == 6 and result["test_runs"] == 1


def test_recovery_leaves_transport_error_terminal():
    def generate(_messages):
        raise AgentTransportError("unreachable")

    def feedback(*_args):
        pytest.fail("terminal transport failure should not request a recovery note")

    provider = SimpleNamespace(generate=generate, safe_metadata=lambda: {})
    result = run_agent(_task(), _workspace(), provider, None, {}, feedback=feedback,
                       feedback_on_protocol_error=True)
    assert result["status"] == "model_transport_error" and result["turns"] == 1


def test_recovery_nomination_is_bound_to_original_trial_bundle():
    history = ROOT / "reports/v3/live-trials.jsonl"
    receipt = recovery_receipt(history, digest(history))
    assert receipt["missed_reminders"] == [{"task_id": "hold-samples", "repeat": 1, "turn": 4}]
    assert receipt["candidates"] == ["reference", "guided-recovery", "compact-guided-recovery"]
    with pytest.raises(ValueError, match="history differs"):
        recovery_receipt(history, "0" * 64)
