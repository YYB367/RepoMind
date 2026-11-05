"""Nominate bounded changes from verified historical development traces."""
import re

from repomind.agent.workspace import digest
from repomind.intelligence.providers import _json_loads
from repomind.platform.tracing import TraceOutbox

REFERENCE = "reference"
POLICIES = {
    REFERENCE: (False, False),
    "compact": (True, False),
    "guided": (False, True),
    "compact-guided": (True, True),
}
RECOVERY_POLICIES = {"guided-recovery": (False, True), "compact-guided-recovery": (True, True)}


def history_receipt(path, expected_sha256):
    if digest(path) != expected_sha256:
        raise ValueError("historical trace bundle differs from frozen protocol")
    traces = TraceOutbox(path).records()
    if not traces:
        raise ValueError("historical trace bundle is empty")
    unfinished = writes = 0
    for trace in traces:
        if (trace.stage != "developer_task" or not trace.synthetic
                or not re.fullmatch(r"dev-[0-9]+", trace.item_id)
                or trace.run_id != "live-dev-r2"):
            raise ValueError("history accepts only the declared V2 development run")
        output = trace.output
        unfinished += (output["public_passed"] and output["hidden_passed"]
                       and output["agent_status"] != "finished")
        writes += sum(obs.name.endswith("_write_file") and obs.metadata.get("status") == "ok"
                      for obs in trace.observations)
    candidates = [REFERENCE]
    candidates += [name for name, (compact, guided) in list(POLICIES.items())[1:]
                   if (not compact or writes) and (not guided or unfinished)]
    return {"sha256": expected_sha256, "traces": len(traces), "run_id": "live-dev-r2",
            "verified_but_unfinished": unfinished, "successful_write_events": writes,
            "candidates": candidates, "kind": "historical_event_replay_for_nomination"}


def recovery_receipt(path, expected_sha256):
    """Read only the frozen prior experiment for evidence of a missed reminder."""
    if digest(path) != expected_sha256:
        raise ValueError("recovery history differs from frozen protocol")
    rows = [_json_loads(line) for line in path.read_bytes().splitlines() if line.strip()]
    misses = []
    for row in rows:
        trial = row["trial"]
        if (row["split"] != "holdout" or trial["policy"] != "guided"
                or not trial["code_verified"] or trial["agent"]["status"] != "turn_budget_exhausted"):
            continue
        calls = trial["model_calls"]
        if len(calls) < 2:
            continue
        budget = _json_loads(calls[0]["input"][1]["content"])["budgets"]["max_turns"]
        error_turn = budget - 2
        if not 1 <= error_turn < len(calls):
            continue
        next_input = _json_loads(calls[error_turn]["input"][-1]["content"])
        if (calls[error_turn - 1]["error_type"] in {"ValueError", "JSONDecodeError", "ValidationError"}
                and next_input.get("protocol_error") and "controller_note" not in next_input):
            misses.append({"task_id": trial["task_id"], "repeat": trial["repeat"], "turn": error_turn})
    if not misses:
        raise ValueError("frozen history has no missed protocol recovery reminder")
    return {"sha256": expected_sha256, "traces": len(rows), "missed_reminders": misses,
            "candidates": [REFERENCE, *RECOVERY_POLICIES], "kind": "prior_protocol_recovery_diagnosis"}


def finish_feedback(observations, remaining):
    if remaining <= 0:
        return None
    written = tested = diffed = -1
    for index, step in enumerate(observations):
        if step["status"] != "ok":
            continue
        if step["tool"] == "write_file":
            written = index
        elif step["tool"] == "run_tests":
            tested = index if step["result"]["passed"] else -1
        elif step["tool"] == "git_diff" and step["result"]["diff"]:
            diffed = index
    if written >= 0 and tested > written and diffed > written:
        return ("Public tests passed and a nonempty diff was inspected after the last write. "
                "If the task requirements are satisfied, send finish as the only action now.")
    if remaining == 2:
        return ("Two model turns remain. If implementation is ready, inspect the diff and run "
                "public tests in one batch, reserving a separate turn for finish.")
    return None
