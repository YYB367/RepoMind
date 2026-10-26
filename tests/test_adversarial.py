"""Independent adversarial checks using synthetic histories, never benchmark answers."""

import json

import pytest
from pydantic import ValidationError

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import Event, MemoryQuery
from repomind.memory.retriever import MemoryRetriever
from repomind.memory.store import ImportValidationError


JAN = "2026-01-01T00:00:00Z"
FEB = "2026-02-01T00:00:00Z"
MAR = "2026-03-01T00:00:00Z"


def event(event_id, value="A", **changes):
    payload = dict(event_id=event_id, project_id="Adversarial", subject="project",
                   predicate="database", value=value, event_type="declare",
                   observed_at=JAN, effective_at=JAN, source_id=f"session-{event_id}")
    payload.update(changes)
    return payload


def write_batch(tmp_path, rows):
    path = tmp_path / "batch.jsonl"
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    return path


def query(store, **changes):
    data = dict(project_id="Adversarial", predicate="database", as_of="2026-12-31")
    data.update(changes)
    return MemoryRetriever(store).query(MemoryQuery(**data))


def ids(result):
    return {item.event_id for item in result.evidence}


def test_parallel_corrections_remain_conflicted_after_one_branch_is_corrected(tmp_path):
    rows = [event("root"), event("left", "B", event_type="correct", observed_at=FEB,
                                supersedes_event_id="root"),
            event("right", "C", event_type="correct", observed_at=FEB,
                  supersedes_event_id="root"),
            event("left-fix", "D", event_type="correct", observed_at=MAR,
                  supersedes_event_id="left")]
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(write_batch(tmp_path, rows))
        answer = query(store)
        assert answer.status == "insufficient_evidence"
        assert answer.value is None
        assert ids(answer) == {"right", "left-fix"}
        assert query(store, known_at=JAN).value == "A"


def test_out_of_order_correction_chain_preserves_later_real_change(tmp_path):
    rows = [event("third", "C", event_type="correct", observed_at=MAR,
                  supersedes_event_id="second"),
            event("new-fact", "D", observed_at="2026-04-01T00:00:00Z",
                  effective_at="2026-04-01T00:00:00Z"),
            event("second", "B", event_type="correct", observed_at=FEB,
                  supersedes_event_id="first"), event("first")]
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(write_batch(tmp_path, rows))
        historical = query(store, as_of="2026-02-15")
        assert historical.value == "C"
        assert ids(historical) == {"third"}
        assert query(store).value == "D"
        assert store.count() == 4


def test_same_instant_conflict_is_not_resolved_by_id_or_import_order(tmp_path):
    rows = [event("zzz", "A"), event("aaa", "B", observed_at=FEB)]
    with SQLiteMemoryStore(":memory:") as first, SQLiteMemoryStore(":memory:") as second:
        first.import_jsonl(write_batch(tmp_path, rows))
        second.import_jsonl(write_batch(tmp_path, list(reversed(rows))))
        a, b = query(first), query(second)
        assert a.status == b.status == "insufficient_evidence"
        assert ids(a) == ids(b) == {"zzz", "aaa"}


def test_parallel_equal_corrections_both_support_the_answer(tmp_path):
    rows = [event("root"), event("fix1", "B", event_type="correct", observed_at=FEB,
                                supersedes_event_id="root"),
            event("fix2", "B", event_type="correct", observed_at=MAR,
                  supersedes_event_id="root")]
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(write_batch(tmp_path, rows))
        answer = query(store)
        assert answer.status == "ok" and answer.value == "B"
        assert ids(answer) == {"fix1", "fix2"}


@pytest.mark.parametrize("different", [{"project_id": "Other"}, {"subject": "service"},
                                       {"predicate": "language"}])
def test_correction_cannot_cross_any_scope_component(tmp_path, different):
    rows = [event("root"), event("bad", "B", event_type="correct", observed_at=FEB,
                                supersedes_event_id="root", **different)]
    with SQLiteMemoryStore(":memory:") as store:
        with pytest.raises(ImportValidationError, match="scope"):
            store.import_jsonl(write_batch(tmp_path, rows))
        assert store.count() == 0


def test_same_observation_time_cycle_is_rejected_atomically(tmp_path):
    rows = [event("one", event_type="correct", supersedes_event_id="two"),
            event("two", event_type="correct", supersedes_event_id="one")]
    with SQLiteMemoryStore(":memory:") as store:
        with pytest.raises(ImportValidationError, match="cycle"):
            store.import_jsonl(write_batch(tmp_path, rows))
        assert store.count() == 0


def test_failed_link_batch_preserves_previous_ledger_and_allows_next_import(tmp_path):
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(write_batch(tmp_path, [event("existing")]))
        rows = [event("valid-new", "B"), event("bad", "C", event_type="correct",
                observed_at=FEB, supersedes_event_id="absent")]
        with pytest.raises(ImportValidationError, match="missing correction target"):
            store.import_jsonl(write_batch(tmp_path, rows))
        assert store.count() == 1
        assert store.get_event("existing").value == "A"
        assert store.get_event("valid-new") is None
        assert store.import_jsonl(write_batch(tmp_path, [event("later", "A")])).imported == 1


def test_timezone_equivalent_same_id_is_idempotent_with_implicit_effective(tmp_path):
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(write_batch(tmp_path, [event("stable")]))
        equivalent = event("stable", observed_at="2026-01-01T08:00:00+08:00")
        del equivalent["effective_at"]
        result = store.import_jsonl(write_batch(tmp_path, [equivalent]))
        assert result.imported == 0 and result.duplicates == 1
        assert store.count() == 1


def test_different_content_same_id_inside_batch_rolls_back(tmp_path):
    with SQLiteMemoryStore(":memory:") as store:
        with pytest.raises(ImportValidationError, match="different content"):
            store.import_jsonl(write_batch(tmp_path, [event("repeat"), event("repeat", "B")]))
        assert store.count() == 0


@pytest.mark.parametrize("kind", ["declare", "complete", "correct"])
def test_actual_future_effective_time_rejected_before_persistence(kind):
    data = event("future", event_type=kind, effective_at=FEB)
    if kind == "correct":
        data["supersedes_event_id"] = "old"
    with pytest.raises(ValidationError, match="cannot be later"):
        Event(**data)


def test_known_at_keeps_exact_microsecond_and_timezone_boundaries(tmp_path):
    rows = [event("original"), event("micro", "B", event_type="correct",
            observed_at="2026-02-01T00:00:00.000001Z", supersedes_event_id="original")]
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(write_batch(tmp_path, rows))
        assert query(store, known_at="2026-02-01T00:00:00Z").value == "A"
        assert query(store, known_at="2026-02-01T08:00:00.000001+08:00").value == "B"
        assert query(store, known_at="2026-02-01T00:00:00.000002Z").value == "B"


def test_date_cutoff_is_utc_end_of_day_not_local_day(tmp_path):
    rows = [event("near-midnight", observed_at="2026-01-02T07:59:59.999999+08:00",
                  effective_at="2026-01-02T07:59:59.999999+08:00"),
            event("next-day", "B", observed_at="2026-01-02T08:00:00+08:00",
                  effective_at="2026-01-02T08:00:00+08:00")]
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(write_batch(tmp_path, rows))
        answer = query(store, as_of="2026-01-01")
        assert answer.value == "A" and ids(answer) == {"near-midnight"}
        assert query(store, as_of="2026-01-02").value == "B"


def test_sql_metacharacters_are_literal_project_subject_predicate_and_ids(tmp_path):
    hostile = "x' OR 1=1; --"
    row = event(hostile, project_id=hostile, subject=hostile, predicate=hostile)
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(write_batch(tmp_path, [row, event("ordinary", "B")]))
        assert query(store).value == "B"
        answer = query(store, project_id=hostile, subject=hostile, predicate=hostile)
        assert answer.value == "A" and ids(answer) == {hostile}
        assert store.get_event("' OR 1=1 --") is None
        assert store.count() == 2


def test_duplicate_json_keys_report_line_and_reject_prior_valid_rows(tmp_path):
    path = tmp_path / "bad-lines.jsonl"
    path.write_text(json.dumps(event("valid")) + '\n{"event_id":"first","event_id":"second"}\n',
                    encoding="utf-8")
    with SQLiteMemoryStore(":memory:") as store:
        with pytest.raises(ImportValidationError) as caught:
            store.import_jsonl(path)
        assert "bad-lines.jsonl:2" in str(caught.value)
        assert "duplicate JSON key" in str(caught.value)
        assert store.count() == 0


@pytest.mark.parametrize("changes", [{"as_of": "2026-01-01T12:00:00"},
                                     {"as_of": 1770000000}, {"project_id": "  "},
                                     {"predicate": None}, {"known_at": "yesterday"}])
def test_invalid_query_values_cannot_reach_store(changes):
    data = dict(project_id="Adversarial", predicate="database", as_of="2026-01-01")
    data.update(changes)
    with pytest.raises(ValidationError):
        MemoryQuery(**data)


def test_raw_json_retains_format_and_unicode_while_identity_is_normalized(tmp_path):
    raw = json.dumps(event("raw", "数据库"), ensure_ascii=False, indent=None, separators=(", ", ": "))
    path = tmp_path / "raw.jsonl"
    path.write_text(raw + "\n", encoding="utf-8")
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(path)
        stored = store.connection.execute("SELECT raw_json FROM events WHERE event_id=?", ("raw",)).fetchone()[0]
        assert stored == raw
        assert query(store).value == "数据库"


def test_correction_cannot_claim_to_observe_target_before_target_observation(tmp_path):
    rows = [event("late", observed_at=MAR),
            event("too-early", "B", event_type="correct", observed_at=FEB,
                  supersedes_event_id="late")]
    with SQLiteMemoryStore(":memory:") as store:
        with pytest.raises(ImportValidationError, match="observed before"):
            store.import_jsonl(write_batch(tmp_path, rows))
        assert store.count() == 0


def test_future_effective_plan_is_visible_only_after_its_observation(tmp_path):
    rows = [event("future-plan", "B", event_type="plan", observed_at=FEB,
                  effective_at="2026-04-01T00:00:00Z")]
    with SQLiteMemoryStore(":memory:") as store:
        store.import_jsonl(write_batch(tmp_path, rows))
        before = query(store, as_of=JAN)
        after = query(store, as_of=FEB)
        audit = query(store, as_of=MAR, known_at=JAN)
        assert before.status == after.status == audit.status == "unknown"
        assert before.plan_event_ids == audit.plan_event_ids == []
        assert after.plan_event_ids == ["future-plan"]
        assert not after.evidence


@pytest.mark.parametrize("timestamp", ["0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-14:00"])
def test_utc_conversion_overflow_is_a_validation_error(timestamp):
    with pytest.raises(ValidationError):
        MemoryQuery(project_id="Adversarial", predicate="database", as_of=timestamp)
    with pytest.raises(ValidationError):
        Event(**event("overflow", observed_at=timestamp, effective_at=timestamp))
