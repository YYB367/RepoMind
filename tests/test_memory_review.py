import hashlib
from pathlib import Path
import sqlite3

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.memory.review import ReviewQueue, read_record
from repomind.cli import main
from repomind.domain.models import Event

STAMP = "2020-01-01T10:00:00+08:00"
PROJECT = "test-project"


def test_review_cli_only_recalls_confirmed_project_facts(tmp_path, capsys):
    import json

    database = tmp_path / "memory.sqlite3"
    source = tmp_path / "test-record.md"
    source.write_text("The default strategy is reference.\n", encoding="utf-8")

    def call(*args, ok=True):
        assert main(["--db", str(database), *args]) == (0 if ok else 2)
        captured = capsys.readouterr()
        return json.loads(captured.out if ok else captured.err)

    def propose(field, value="reference", quote="default strategy is reference"):
        return call("review", "propose", str(source), "--project", PROJECT, "--subject", "harness",
                    "--recorded-at", STAMP, "--quote", quote, "--field", field, "--value", value,
                    "--event-type", "declare")

    def query(field, project=PROJECT, *extra):
        return call("query", "--project", project, "--subject", "harness", "--field", field,
                    "--as-of", "2030-01-01", "--with-sources", *extra)

    created = propose("default_strategy", value="draft")
    candidate = created["candidate"]
    cid = candidate["candidate_id"]
    assert created["created"] and candidate["status"] == "pending"
    assert query("default_strategy")["status"] == "unknown"
    assert call("review", "list", "--project", "unrelated") == {"candidates": []}
    assert "not found" in call("review", "show", cid, "--project", "unrelated", ok=False)["message"]
    edit = call("review", "edit", cid, "--project", PROJECT, "--revision", "1", "--value", "reference")
    assert edit["revision"] == 2
    assert "revision" in call("review", "confirm", cid, "--project", PROJECT, "--revision", "1", ok=False)["message"]
    assert query("default_strategy")["status"] == "unknown"
    approved = call("review", "confirm", cid, "--project", PROJECT, "--revision", "2")
    assert approved["status"] == "confirmed"
    assert call("review", "confirm", cid, "--project", PROJECT, "--revision", "2") == approved
    assert propose("default_strategy", "draft") == {"created": False, "candidate": approved}
    answer = query("default_strategy")
    assert answer["value"] == "reference"
    assert answer["evidence"][0]["effective_at"] == "2020-01-01T02:00:00Z"
    artifact = answer["sources"][0]["artifact"]
    assert artifact["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert artifact["path"] == source.as_posix()
    assert answer["sources"][0]["provenance"]["evidence_text"] == "default strategy is reference"
    assert query("default_strategy", "unrelated")["sources"] == []
    assert query("default_strategy", PROJECT, "--known-at", STAMP)["status"] == "unknown"

    rejected = propose("experiment_only")["candidate"]
    rid = rejected["candidate_id"]
    denied = call("review", "reject", rid, "--project", PROJECT, "--revision", "1")
    assert denied["status"] == "rejected" and denied["event_id"] is None
    assert propose("experiment_only") == {"created": False, "candidate": denied}
    assert "final review" in call("review", "confirm", rid, "--project", PROJECT, "--revision", "1", ok=False)["message"]
    assert query("experiment_only")["status"] == "unknown"
    with SQLiteMemoryStore(database) as store:
        assert store.count() == 1
        assert store.get_source(PROJECT, rejected["draft"]["source_id"]) is None


def test_atomic_confirmation_rolls_back_event_and_provenance(tmp_path):
    source = tmp_path / "report.md"
    source.write_text("selected excerpt", encoding="utf-8")
    database = tmp_path / "memory.sqlite3"
    with SQLiteMemoryStore(database) as store:
        queue = ReviewQueue(store)
        artifact = read_record(source, commit=None, repo=tmp_path, recorded_at=STAMP, quote="excerpt")
        candidate, _ = queue.propose(artifact=artifact, quote="excerpt", project_id=PROJECT, subject="project",
                                     predicate="test", value="true", event_type="complete", effective_at=None)
        store.connection.execute("""CREATE TRIGGER fail_review BEFORE UPDATE ON memory_review_candidates
            BEGIN SELECT RAISE(ABORT, 'injected review failure'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="injected"):
            queue.decide(PROJECT, candidate.candidate_id, 1, decision="confirmed")
        assert store.count() == 0
        assert store.get_source(PROJECT, candidate.draft.source_id) is None
        assert store.get_provenance(candidate.draft.event_id) is None
        assert queue.show(PROJECT, candidate.candidate_id).status == "pending"
        store.connection.execute("DROP TRIGGER fail_review")
        assert queue.decide(PROJECT, candidate.candidate_id, 1, decision="confirmed").status == "confirmed"


def test_invalid_quote_does_not_create_a_candidate(tmp_path):
    source = tmp_path / "report.md"
    source.write_text("real source", encoding="utf-8")
    with pytest.raises(ValueError, match="exact substring"):
        read_record(source, commit=None, repo=tmp_path, recorded_at=STAMP, quote="invented quote")


def test_existing_ledger_accepts_additive_review_schema(tmp_path):
    db = tmp_path / "existing.sqlite3"
    event = Event(event_id="old", project_id=PROJECT, subject="project", predicate="old", value="preserved",
                  event_type="declare", observed_at=STAMP, source_id="old-source")
    with SQLiteMemoryStore(db) as store:
        assert store.import_events([event]).imported == 1
    with SQLiteMemoryStore(db) as store:
        assert ReviewQueue(store).list(PROJECT, None) == []
        assert store.get_event("old") == event
        assert store.connection.execute("PRAGMA user_version").fetchone()[0] == 2
