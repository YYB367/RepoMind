"""Finite V4.2 candidates nominated from actual, frozen RepoMind pilot evidence."""
from copy import deepcopy

from repomind.agent.workspace import digest
from repomind.intelligence.providers import _json_loads

PILOT_POLICIES = {"focused-evidence": False, "focused-evidence-compact": True}


def pilot_receipt(path, expected_sha256):
    if digest(path) != expected_sha256:
        raise ValueError("pilot evidence differs from frozen protocol")
    record = _json_loads(path.read_bytes())
    key = ("codex", "v4_acceptance_path")
    facts = record.get("recalled", [])
    matching = [row for row in facts if (row.get("subject"), row.get("field")) == key]
    unrelated = [row for row in facts if (row.get("subject"), row.get("field")) != key]
    if (record.get("mode") != "codex_exec_wrapper" or not record.get("session_id")
            or "codex.v4_acceptance_path" not in record.get("task_prompt", "")
            or len(matching) != 1 or not unrelated
            or any(not row.get("source_id") or not row.get("sha256") for row in facts)):
        raise ValueError("pilot has no verifiable explicit-key context redundancy")
    return {"kind":"real_pilot_context_redundancy", "sha256":expected_sha256,
            "session_id":record["session_id"], "requested_key":list(key),
            "recalled_facts":len(facts), "unrelated_facts":len(unrelated),
            "source_ids":[row["source_id"] for row in facts],
            "candidates":["reference", *PILOT_POLICIES]}


def task_context(task, snapshot, *, focused):
    if snapshot.get("project_id") != task.project_id:
        raise ValueError("pilot memory snapshot belongs to another project")
    context = deepcopy(snapshot)
    if focused and task.memory_keys:
        keys = set(task.memory_keys)
        context["facts"] = [row for row in context["facts"] if (row["subject"],row["field"]) in keys]
    return context
