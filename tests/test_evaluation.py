"""Evaluation tests use independent synthetic examples, never the holdout set."""

import hashlib
import json

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import Event, MemoryQuery, QueryResult
from repomind.evaluation.metrics import score_answer, summarize
from repomind.evaluation.runner import load_questions, run_evaluation


def event(event_id="current", **changes):
    payload = {
        "event_id": event_id,
        "project_id": "A",
        "subject": "project",
        "predicate": "database",
        "value": "PostgreSQL",
        "event_type": "declare",
        "observed_at": "2026-02-01T00:00:00Z",
        "source_id": "session-feb",
    }
    payload.update(changes)
    return Event.model_validate(payload)


def write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def ledger(tmp_path):
    records = [
        event("old", value="MySQL", observed_at="2026-01-01T00:00:00Z"),
        event(),
        event("other-project", project_id="B", value="SQLite"),
        event("worker-db", subject="worker", value="MongoDB"),
        event("plan", event_type="plan", value="Oracle", observed_at="2026-03-01T00:00:00Z", effective_at="2026-04-01T00:00:00Z"),
        event("late", predicate="language", observed_at="2026-04-01T00:00:00Z", effective_at="2026-01-01T00:00:00Z", value="Python"),
    ]
    path = write_jsonl(tmp_path / "events.jsonl", [record.model_dump(mode="json") for record in records])
    with SQLiteMemoryStore(tmp_path / "memory.sqlite3") as store:
        store.import_jsonl(path)
        yield store


def query(**changes):
    payload = {"project_id": "A", "predicate": "database", "as_of": "2026-03-15"}
    payload.update(changes)
    return MemoryQuery.model_validate(payload)


def actual(store, *, ids=("current",), considered=("old", "current", "plan"), value="PostgreSQL", status="ok"):
    return QueryResult(status=status, value=value, evidence=[store.get_event(key) for key in ids], reason="synthetic scoring fixture", considered_event_ids=list(considered))


GOLD = {"status": "ok", "value": "PostgreSQL", "event_ids": ["current"]}


def test_score_accepts_correct_answer_and_audited_citation(ledger):
    score = score_answer(query(), GOLD, actual(ledger), ledger)
    assert score["passed"]
    assert score["failure_stage"] is None
    assert score["citation_valid"] == score["citation_total"] == 1


def test_score_detects_resolution_error_when_evidence_was_retrieved(ledger):
    score = score_answer(query(), GOLD, actual(ledger, value="MySQL"), ledger)
    assert not score["passed"]
    assert score["failure_stage"] == "resolution"
    assert score["missing_candidate_event_ids"] == []


def test_score_distinguishes_missing_retrieval_candidates(ledger):
    result = actual(ledger, ids=(), considered=(), value=None, status="unknown")
    score = score_answer(query(), GOLD, result, ledger)
    assert score["failure_stage"] == "retrieval"
    assert score["missing_candidate_event_ids"] == ["current"]


def test_score_rejects_right_value_with_wrong_historical_evidence(ledger):
    score = score_answer(query(), GOLD, actual(ledger, ids=("old",)), ledger)
    assert score["answer_correct"]
    assert not score["evidence_correct"]
    assert score["failure_stage"] == "provenance"


@pytest.mark.parametrize("changed", [{"source_id": "invented-session"}, {"event_id": "invented-event"}])
def test_score_rejects_forged_source_or_event(ledger, changed):
    cited = ledger.get_event("current").model_copy(update=changed)
    result = actual(ledger).model_copy(update={"evidence": [cited]})
    score = score_answer(query(), GOLD, result, ledger)
    assert score["failure_stage"] == "provenance"
    assert score["citation_valid"] == 0
    assert score["citation_issues"]


@pytest.mark.parametrize("ids,considered", [(("other-project",), ("current",)), (("current",), ("current", "other-project"))])
def test_score_counts_cross_project_citation_and_candidate_leakage(ledger, ids, considered):
    score = score_answer(query(), GOLD, actual(ledger, ids=ids, considered=considered), ledger)
    assert score["project_leakage"]
    assert score["leaked_event_ids"] == ["other-project"]
    assert score["failure_stage"] == "provenance"


def test_score_detects_leakage_even_if_citation_project_was_forged(ledger):
    cited = ledger.get_event("other-project").model_copy(update={"project_id": "A"})
    result = actual(ledger).model_copy(update={"evidence": [cited]})
    score = score_answer(query(), GOLD, result, ledger)
    assert score["project_leakage"]
    assert score["leaked_event_ids"] == ["other-project"]
    assert score["citation_valid"] == 0


@pytest.mark.parametrize("ids", [("worker-db",), ("plan",), ("current", "current")])
def test_score_rejects_wrong_scope_plan_or_duplicate_citations(ledger, ids):
    score = score_answer(query(), GOLD, actual(ledger, ids=ids), ledger)
    assert not score["passed"]
    assert score["failure_stage"] == "provenance"
    assert score["citation_issues"]


def test_score_checks_known_at_visibility(ledger):
    q = query(predicate="language", known_at="2026-02-15")
    score = score_answer(q, {"status": "unknown", "value": None, "event_ids": []}, actual(ledger, ids=("late",), value="Python"), ledger)
    assert score["failure_stage"] == "provenance"
    assert "known_at" in score["citation_issues"][0]["reason"]


def test_metric_denominators_for_unknown_and_empty_citations(ledger):
    q = query(predicate="missing")
    answer = score_answer(q, {"status": "unknown", "value": None, "event_ids": []}, actual(ledger, ids=(), considered=(), value=None, status="unknown"), ledger)
    summary = summarize([{"category": "unknown", "passed": True, "answers": [answer]}], 0.25)
    assert summary["unknown_information_handling_rate"] == 1
    assert summary["unknown_expected_count"] == 1
    assert summary["source_citation_correctness"] is None
    assert summary["citation_total"] == 0
    assert summary["runtime_seconds"] == 0.25


def question(question_id="q1", **changes):
    payload = {"question_id": question_id, "category": "basic", "description": "Independent synthetic question", "queries": [{"project_id": "A", "predicate": "database", "as_of": "2026-03-15"}], "expected": [GOLD]}
    payload.update(changes)
    return payload


@pytest.mark.parametrize("records,needle", [
    ([], "empty"),
    ([question(), question()], "duplicate question_id"),
    ([question(expected=[])], "expected"),
    ([question(category="unrecognized")], "category"),
    ([question(expected=[{"status": "ok", "value": "PostgreSQL", "event_ids": ["current", "current"]}])], "unique"),
])
def test_dataset_validation_has_diagnosable_errors(tmp_path, records, needle):
    path = write_jsonl(tmp_path / "invalid.jsonl", records)
    with pytest.raises(ValueError, match=needle) as raised:
        load_questions(path)
    assert str(path) in str(raised.value)


def test_dataset_rejects_duplicate_json_keys_with_line_number(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text('{"question_id":"q1","question_id":"q2"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key") as raised:
        load_questions(path)
    assert f"{path}:1:" in str(raised.value)


def test_runner_writes_both_formats_with_hashes_and_compound_scoring(tmp_path):
    records = [event(), event("cache", predicate="cache", value="Redis", source_id="separate-session")]
    events_path = write_jsonl(tmp_path / "events.jsonl", [e.model_dump(mode="json") for e in records])
    compound = question("compound", category="cross_session", queries=[query().model_dump(mode="json"), query(predicate="cache").model_dump(mode="json")], expected=[GOLD, {"status": "ok", "value": "Redis", "event_ids": ["cache"]}])
    dataset_path = write_jsonl(tmp_path / "questions.jsonl", [question(), compound])
    output = tmp_path / "reports" / "report.md"
    report = run_evaluation(events_path, dataset_path, output)
    assert report["metrics"]["correct"] == report["metrics"]["total"] == 2
    assert report["metrics"]["query_total"] == 3
    assert report["metrics"]["source_citation_correctness"] == 1
    assert report["metrics"]["project_leakage_count"] == 0
    assert report["config"]["events_sha256"] == hashlib.sha256(events_path.read_bytes()).hexdigest()
    assert report["config"]["dataset_sha256"] == hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    assert json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))["metrics"] == report["metrics"]
    assert "Cross-project leakage" in output.read_text(encoding="utf-8")
    assert report["failures"] == []


def test_compound_question_fails_when_only_one_clause_is_wrong(tmp_path):
    events_path = write_jsonl(tmp_path / "events.jsonl", [event().model_dump(mode="json")])
    compound = question("compound", category="cross_session", queries=[query().model_dump(mode="json"), query().model_dump(mode="json")], expected=[GOLD, {"status": "ok", "value": "Oracle", "event_ids": ["current"]}])
    dataset_path = write_jsonl(tmp_path / "questions.jsonl", [compound])
    report = run_evaluation(events_path, dataset_path, tmp_path / "report.json")
    assert report["metrics"]["correct"] == 0
    assert report["failures"][0]["answers"][0]["passed"]
    assert report["failures"][0]["answers"][1]["failure_stage"] == "resolution"


def test_latest_observation_baseline_exposes_plan_error(tmp_path):
    records = [event(), event("plan", event_type="plan", value="Oracle", observed_at="2026-03-01T00:00:00Z", effective_at="2026-04-01T00:00:00Z")]
    events_path = write_jsonl(tmp_path / "events.jsonl", [e.model_dump(mode="json") for e in records])
    dataset_path = write_jsonl(tmp_path / "questions.jsonl", [question()])
    good = run_evaluation(events_path, dataset_path, tmp_path / "rules.md")
    baseline = run_evaluation(events_path, dataset_path, tmp_path / "baseline.md", baseline=True)
    assert good["metrics"]["correct"] == 1
    assert baseline["metrics"]["correct"] == 0
    assert baseline["strategy"] == "latest_observation_baseline"
    assert baseline["metrics"]["source_citation_correctness"] == 0


def test_runner_rejects_output_overwriting_inputs(tmp_path):
    path = write_jsonl(tmp_path / "events.json", [event().model_dump(mode="json")])
    dataset = write_jsonl(tmp_path / "questions.jsonl", [question()])
    with pytest.raises(ValueError, match="overwrite"):
        run_evaluation(path, dataset, path)
    with pytest.raises(ValueError, match="end in"):
        run_evaluation(path, dataset, tmp_path / "report.txt")
