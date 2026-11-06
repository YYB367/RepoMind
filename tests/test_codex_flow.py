from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.codex_cli import _hooks_config, _run
from repomind.codex_flow import capture, hook, recall
from repomind.memory.review import ReviewQueue


def _message(path="handoff.md", *, quote="Handoff label: ledger-forest", field="handoff_label", value="ledger-forest"):
    return "Finished.\n" + chr(96) * 3 + "repomind-memory\n" + json.dumps([{
        "path": path, "quote": quote, "subject": "codex", "field": field, "value": value,
        "event_type": "declare",
    }]) + "\n" + chr(96) * 3


def test_stop_capture_and_prompt_recall_are_review_gated(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "handoff.md").write_text("Handoff label: ledger-forest", encoding="utf-8")
    database = tmp_path / "review.sqlite3"
    stop = {"hook_event_name": "Stop", "cwd": str(root), "session_id": "session-A",
            "last_assistant_message": _message(), "transcript_path": str(tmp_path / "private.jsonl")}
    output, receipt = hook(root, database, "RepoMind", stop)
    assert "pending" in output["systemMessage"] and receipt["session_id"] == "session-A"
    candidate_id, = receipt["pending_ids"]
    assert hook(root, database, "RepoMind", stop)[1]["created"] == 0
    assert recall(database, "RepoMind", "Codex handoff label") == []

    with SQLiteMemoryStore(database) as store:
        queue = ReviewQueue(store)
        queue.decide("RepoMind", candidate_id, 1, decision="confirmed")
        assert store.count() == 1
    prompt = {"hook_event_name": "UserPromptSubmit", "cwd": str(root), "session_id": "session-B",
              "prompt": "Codex handoff label"}
    output, receipt = hook(root, database, "RepoMind", prompt)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "ledger-forest" in context and "handoff.md" in context
    assert receipt["recalled_source_ids"][0].startswith("review-source-")
    assert recall(database, "OtherProject", "handoff label") == []
    assert recall(database, "RepoMind", "unrelated climate forecast") == []
    assert hook(root, database, "RepoMind", prompt | {"cwd": str(tmp_path)}) == ({}, None)


def test_stop_rejects_unverified_and_outside_evidence(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "handoff.md").write_text("Handoff label: ledger-forest", encoding="utf-8")
    (tmp_path / "outside.md").write_text("Handoff label: ledger-forest", encoding="utf-8")
    database = tmp_path / "review.sqlite3"
    for message in (_message("../outside.md"), _message(".env"), _message(quote="fabricated")):
        assert capture(root, database, "RepoMind", message) == {"pending_ids": [], "created": 0, "skipped": 1}
    assert capture(root, database, "RepoMind", _message() + "\nA note after the marker")["created"] == 0
    assert not database.exists()


def test_rejected_candidate_never_enters_readonly_recall(tmp_path):
    (tmp_path / "handoff.md").write_text("Handoff label: ledger-forest", encoding="utf-8")
    database = tmp_path / "review.sqlite3"
    cid, = capture(tmp_path, database, "RepoMind", _message())["pending_ids"]
    with SQLiteMemoryStore(database) as store:
        ReviewQueue(store).decide("RepoMind", cid, 1, decision="rejected")
    assert recall(database, "RepoMind", "handoff label") == []
    with SQLiteMemoryStore(database, read_only=True) as store:
        assert store.count() == 0
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_wrapper_uses_real_exec_contract_and_distinct_session_input(tmp_path, monkeypatch):
    (tmp_path / "handoff.md").write_text("Handoff label: ledger-forest", encoding="utf-8")
    db = tmp_path / "review.sqlite3"
    prompts = []

    def fake_run(argv, *, input, **kwargs):
        assert argv[:3] == ["codex", "exec", "--json"]
        prompts.append(input)
        n = len(prompts)
        events = [
            {"type": "thread.started", "thread_id": f"session-{n}"},
            {"type": "item.completed", "item": {"type": "agent_message",
                                              "text": _message() if n == 1 else "Used the handoff label."}},
            {"type": "turn.completed"},
        ]
        return SimpleNamespace(returncode=0, stdout="\n".join(map(json.dumps, events)), stderr="")

    monkeypatch.setattr("repomind.codex_cli.subprocess.run", fake_run)
    a = _run(tmp_path, db, "RepoMind", "Prepare a handoff note.")
    assert a["recalled"] == []
    cid, = a["capture"]["pending_ids"]
    with SQLiteMemoryStore(db) as store:
        ReviewQueue(store).decide("RepoMind", cid, 1, decision="confirmed")
    b = _run(tmp_path, db, "RepoMind", "Use the Codex handoff label.")
    assert a["session_id"] != b["session_id"] and b["recalled"][0]["value"] == "ledger-forest"
    assert "ledger-forest" in prompts[1] and "handoff.md" in prompts[1]
    assert b["capture"]["pending_ids"] == []
