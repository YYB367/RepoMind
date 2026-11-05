"""Nominate bounded changes from verified historical development traces."""
import re

from repomind.agent.workspace import digest
from repomind.platform.tracing import TraceOutbox

REFERENCE = "reference"
POLICIES = {
    REFERENCE: (False, False),
    "compact": (True, False),
    "guided": (False, True),
    "compact-guided": (True, True),
}


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
