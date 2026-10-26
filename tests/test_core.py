import json
import sqlite3

import pytest
from pydantic import ValidationError

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import Event, MemoryQuery
from repomind.memory.store import ImportValidationError


def event(event_id="e1", **changes):
    data = dict(event_id=event_id, project_id="A", subject="project", predicate="database",
                value="MySQL", event_type="declare", observed_at="2026-01-01T00:00:00Z", source_id="session-1")
    data.update(changes)
    return data


def write_jsonl(tmp_path, rows):
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
    return path


@pytest.mark.parametrize("changes", [
    {"project_id": " "}, {"value": 42}, {"source_id": ""}, {"event_type": "guess"},
    {"observed_at": "2026-01-01"}, {"observed_at": "2026-01-01T00:00:00"},
    {"observed_at": 1767225600}, {"effective_at": "2026-02-01T00:00:00Z"},
    {"event_type": "correct"}, {"supersedes_event_id": "another"}, {"unexpected": True},
])
def test_reject_invalid_event(changes):
    with pytest.raises(ValidationError):
        Event.model_validate(event(**changes))


def test_normalize_time_and_default_effective():
    e = Event.model_validate(event(observed_at="2026-01-01T08:00:00+08:00"))
    assert e.effective_at == e.observed_at
    assert e.observed_at.isoformat() == "2026-01-01T00:00:00+00:00"
    query = MemoryQuery(project_id="A", predicate="database", as_of="2026-01-01")
    assert query.as_of.isoformat() == "2026-01-01T23:59:59.999999+00:00"


def test_persist_idempotent_and_retain_raw(tmp_path):
    path = write_jsonl(tmp_path, [event()])
    database = tmp_path / "memory.db"
    with SQLiteMemoryStore(database) as store:
        assert store.import_jsonl(path).model_dump() == {"imported": 1, "duplicates": 0}
        assert store.import_jsonl(path).model_dump() == {"imported": 0, "duplicates": 1}
        assert json.loads(store.connection.execute("SELECT raw_json FROM events").fetchone()[0]) == event()
    with SQLiteMemoryStore(database) as restarted:
        assert restarted.count() == 1
        assert restarted.get_event("e1").source_id == "session-1"


def test_conflicting_id_rolls_back_whole_batch(tmp_path):
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        store.import_jsonl(write_jsonl(tmp_path, [event()]))
        with pytest.raises(ImportValidationError, match="different content"):
            store.import_jsonl(write_jsonl(tmp_path, [event("new"), event(value="PostgreSQL")]))
        assert store.count() == 1
        assert store.get_event("new") is None


def test_invalid_json_line_atomic_and_diagnostic(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(event()) + "\n{broken}", encoding="utf-8")
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        with pytest.raises(ImportValidationError, match=r"bad.jsonl:2"):
            store.import_jsonl(path)
        assert store.count() == 0


def test_scope_and_parameter_binding(tmp_path):
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        store.import_jsonl(write_jsonl(tmp_path, [event(), event("b", project_id="B"),
                                                 event("c", subject="worker")]))
        q = MemoryQuery(project_id="A", predicate="database", as_of="2026-02-01")
        assert [e.event_id for e in store.list_events(q)] == ["e1"]
        q = MemoryQuery(project_id="A' OR 1=1 --", predicate="database", as_of="2026-02-01")
        assert store.list_events(q) == []


def test_forward_correction_reference_and_audit_preserved(tmp_path):
    correction = event("e2", event_type="correct", value="MariaDB", observed_at="2026-02-01T00:00:00Z",
                       effective_at="2026-01-01T00:00:00Z", supersedes_event_id="e1")
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        assert store.import_jsonl(write_jsonl(tmp_path, [correction, event()])).imported == 2
        assert store.get_event("e1").value == "MySQL"
        assert store.get_event("e2").supersedes_event_id == "e1"


@pytest.mark.parametrize("target_changes, correction_changes", [
    ({}, {"supersedes_event_id": "missing"}),
    ({"project_id": "B"}, {}),
    ({"event_type": "plan"}, {}),
    ({}, {"effective_at": "2026-01-02T00:00:00Z"}),
])
def test_bad_correction_links_rejected_atomically(tmp_path, target_changes, correction_changes):
    correction = event("e2", event_type="correct", value="MariaDB", observed_at="2026-02-01T00:00:00Z",
                       effective_at="2026-01-01T00:00:00Z", supersedes_event_id="e1")
    correction.update(correction_changes)
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        with pytest.raises(ImportValidationError):
            store.import_jsonl(write_jsonl(tmp_path, [event(**target_changes), correction]))
        assert store.count() == 0


def test_future_schema_is_not_modified(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError, match="unsupported database schema"):
        SQLiteMemoryStore(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
