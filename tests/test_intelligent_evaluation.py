"""Independent synthetic gold checks; no V1.1 holdout or paid HTTP requests."""

from copy import deepcopy
import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import Event, QueryResult
from repomind.evaluation import intelligent
from repomind.evaluation.intelligent import IntelligentCase, IntelligentQuery, load_intelligent_cases, run_intelligent_evaluation, score_extraction, score_search_response
from repomind.intelligence.extraction import Extractor
from repomind.intelligence.models import ExtractionBatch, SourceMessage
from repomind.intelligence.providers import ProviderConfig


def write_jsonl(path, records):
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    return path


def fact(value="MySQL", *, event_type="declare", effective_at="2026-03-01T00:00:00Z", quote="database MySQL", **changes):
    data = {"subject": "project", "predicate": "database", "value": value, "event_type": event_type,
            "effective_at": effective_at, "supersedes_event_id": None, "evidence_text": quote}
    data.update(changes)
    return data


def query(text="database", *, date="2026-03-15", value="MySQL", sources=("source-1",), key=("project", "database"), status="ok", **changes):
    data = {"project_id": "A", "text": text, "as_of": date, "expected_key": list(key) if key is not None else None,
            "expected_status": status, "expected_value": value, "expected_source_ids": list(sources)}
    data.update(changes)
    return data


@pytest.fixture
def benchmark(tmp_path, monkeypatch):
    # Environment loading, if a future regression accidentally invokes it, sees
    # only this empty synthetic directory, never the real project .env.
    monkeypatch.chdir(tmp_path)
    cases = [
        {"case_id": "c1", "source": {"project_id": "A", "source_id": "source-1", "observed_at": "2026-03-01T00:00:00Z",
                                     "text": "A database MySQL; plan PostgreSQL on 2026-04-01T00:00:00Z."},
         "expected_facts": [fact(), fact("PostgreSQL", event_type="plan", effective_at="2026-04-01T00:00:00Z", quote="plan PostgreSQL")],
         "queries": [query(), query("database after migration", date="2026-04-10", value="PostgreSQL", sources=("source-2",))]},
        {"case_id": "c2", "source": {"project_id": "A", "source_id": "source-2", "observed_at": "2026-04-05T00:00:00Z",
                                     "text": "A completed database PostgreSQL at 2026-04-01T00:00:00Z."},
         "expected_facts": [fact("PostgreSQL", event_type="complete", effective_at="2026-04-01T00:00:00Z", quote="completed database PostgreSQL")],
         "queries": [query("database now", date="2026-04-10", value="PostgreSQL", sources=("source-2",)), query("previous database")]},
        {"case_id": "c3", "source": {"project_id": "A", "source_id": "source-3", "observed_at": "2026-04-06T00:00:00Z",
                                     "text": "Should we add a cache? No fact was adopted."},
         "expected_facts": [], "queries": [query("cache", key=None, value=None, sources=(), status="unknown")]},
    ]
    seed = {"event_id": "seed-db", "project_id": "A", "source_id": "seed", "observed_at": "2026-01-01T00:00:00Z",
            "subject": "project", "predicate": "database", "value": "SQLite", "event_type": "declare"}
    gold = [seed]
    responses = []
    for case in cases:
        source = SourceMessage.model_validate(case["source"])
        recorded_facts = deepcopy(case["expected_facts"])
        # Record an alternative, longer quote: correctness does not require the
        # oracle's unique substring. Omitted declare time exercises defaulting.
        for number, expected in enumerate(case["expected_facts"]):
            gold.append({"event_id": f"manual-gold-{case['case_id']}-{number}", "project_id": source.project_id,
                         "source_id": source.source_id, "observed_at": source.observed_at.isoformat(),
                         **{name: expected[name] for name in ("subject", "predicate", "value", "event_type", "effective_at", "supersedes_event_id")}})
            if expected["event_type"] == "declare":
                recorded_facts[number]["effective_at"] = None
        if recorded_facts:
            recorded_facts[0]["evidence_text"] = source.text
        responses.append({"source_sha256": source.content_hash,
                          "response": {"facts": recorded_facts, "abstain_reason": None if recorded_facts else "No adopted fact."}})
    files = {"seeds": write_jsonl(tmp_path / "seeds.jsonl", [seed]), "gold": write_jsonl(tmp_path / "gold.jsonl", gold),
             "dataset": write_jsonl(tmp_path / "cases.jsonl", cases), "responses": write_jsonl(tmp_path / "responses.jsonl", responses)}
    return files, cases, responses, gold


def run(files, output, **changes):
    return run_intelligent_evaluation(files["seeds"], files["gold"], files["dataset"], output, responses_path=files["responses"], **changes)


def test_independent_stages_ingest_all_sources_before_queries_and_write_hash_reports(benchmark, tmp_path):
    files, cases, responses, gold = benchmark
    report = run(files, tmp_path / "reports" / "result.md")
    assert report["metrics"]["all_passed"]
    assert report["metrics"]["release_gate_passed"]
    assert report["metrics"]["extraction"]["precision"] == report["metrics"]["extraction"]["recall"] == 1
    assert report["metrics"]["extraction"]["exact_cases"] == 3
    assert report["metrics"]["retrieval"]["recalled_at_3"] == report["metrics"]["retrieval"]["key_queries"] == 4
    assert report["metrics"]["end_to_end"]["correct"] == 5
    assert report["metrics"]["end_to_end"]["unknown_expected_count"] == 1
    assert report["metrics"]["source_validity"] == 1
    assert report["metrics"]["project_leakage_count"] == 0
    assert report["validation"]["offline_test_double"]
    assert report["validation"]["status"] == "partial"
    assert not report["validation"]["live_extraction"]
    assert not report["validation"]["real_semantic_quality"]
    assert report["config"]["inputs"]["dataset"]["sha256"] == hashlib.sha256(files["dataset"].read_bytes()).hexdigest()
    assert report["config"]["inputs"]["gold_events"]["sha256"] == hashlib.sha256(files["gold"].read_bytes()).hexdigest()
    assert report["config"]["top_k"] == 3
    assert report["config"]["python_version"]
    assert report["failures"] == []
    md = (tmp_path / "reports" / "result.md").read_text(encoding="utf-8")
    data = json.loads((tmp_path / "reports" / "result.json").read_text(encoding="utf-8"))
    assert md.startswith("# 阶段目标：")
    assert list(data)[0] == "stage_goal"
    assert data["metrics"] == report["metrics"]


def test_wrong_extraction_does_not_contaminate_gold_retrieval_or_adjust_gold(benchmark, tmp_path):
    files, cases, responses, gold = benchmark
    original_gold_hash = hashlib.sha256(files["gold"].read_bytes()).hexdigest()
    responses[0]["response"]["facts"][0]["value"] = "Oracle"
    write_jsonl(files["responses"], responses)
    report = run(files, tmp_path / "wrong.md")
    assert not report["metrics"]["all_passed"]
    assert report["metrics"]["extraction"]["precision"] == pytest.approx(2 / 3)
    assert report["metrics"]["extraction"]["recall"] == pytest.approx(2 / 3)
    assert report["metrics"]["retrieval"]["accuracy"] == 1
    assert report["metrics"]["end_to_end"]["accuracy"] < 1
    assert any(item["stage"] == "extraction" for item in report["failures"])
    assert any(item["stage"] == "end_to_end" and item["details"]["failure_stage"] == "extraction" for item in report["failures"])
    assert hashlib.sha256(files["gold"].read_bytes()).hexdigest() == original_gold_hash


def test_missing_replay_response_is_recorded_as_case_failure_even_for_empty_gold(benchmark, tmp_path):
    files, cases, responses, gold = benchmark
    write_jsonl(files["responses"], responses[:2])
    report = run(files, tmp_path / "missing.json")
    assert not report["metrics"]["all_passed"]
    failed = [case for case in report["extraction_cases"] if case["case_id"] == "c3"][0]
    assert not failed["passed"]
    assert failed["expected_count"] == failed["predicted_count"] == 0
    assert "no recorded extraction" in failed["error"]


def test_extraction_quote_need_not_equal_gold_quote_but_must_be_verbatim(benchmark):
    files, cases, responses, gold = benchmark
    case = IntelligentCase.model_validate(cases[0])
    class Provider:
        name = "synthetic-test-only"
        def extract(self, source, context):
            return ExtractionBatch.model_validate(responses[0]["response"])
    memory = Extractor(Provider()).extract(case.source)
    score = score_extraction(case, memory)
    assert score["passed"]
    first = memory.events[0].event_id
    changed = memory.model_copy(update={"evidence_by_event": {**memory.evidence_by_event, first: "forged quote"}})
    score = score_extraction(case, changed)
    assert not score["passed"]
    assert score["quote_valid"] < score["quote_total"]


def test_strict_all_passed_can_fail_while_predeclared_numeric_gate_still_passes(benchmark, tmp_path, monkeypatch):
    files, cases, responses, gold = benchmark
    original = intelligent.HybridMemorySearch.search
    changed = False
    def wrong_once(self, *args, **kwargs):
        nonlocal changed
        response = original(self, *args, **kwargs)
        db_name = self.store.connection.execute("PRAGMA database_list").fetchone()[2]
        if not changed and db_name.endswith("actual.sqlite3") and response["hits"]:
            changed = True
            response["hits"][0]["result"]["value"] = "Oracle"
        return response
    monkeypatch.setattr(intelligent.HybridMemorySearch, "search", wrong_once)
    report = run(files, tmp_path / "one-wrong.md")
    assert report["metrics"]["end_to_end"]["accuracy"] == 0.8
    assert report["metrics"]["release_gate_passed"]
    assert not report["metrics"]["all_passed"]
    assert any(item["details"]["failure_stage"] == "resolution" for item in report["failures"])
    assert report["config"]["release_thresholds"] == intelligent.RELEASE_THRESHOLDS


def test_scorer_distinguishes_missing_key_wrong_resolution_and_forged_source(benchmark, tmp_path):
    files, cases, responses, gold = benchmark
    q = IntelligentQuery.model_validate(cases[0]["queries"][0])
    with SQLiteMemoryStore(tmp_path / "score.sqlite3") as store:
        store.import_jsonl(files["gold"])
        response = intelligent.HybridMemorySearch(store).search(q.project_id, q.text, q.as_of, mode="lexical", top_k=3)
        assert score_search_response(q, response, store)["passed"]
        missing = {"project_id": "A", "hits": []}
        assert score_search_response(q, missing, store)["failure_stage"] == "retrieval"
        wrong = deepcopy(response)
        wrong["hits"][0]["result"]["value"] = "Oracle"
        assert score_search_response(q, wrong, store)["failure_stage"] == "resolution"
        forged = deepcopy(response)
        forged["hits"][0]["result"]["evidence"][0]["source_id"] = "forged-source"
        invalid = score_search_response(q, forged, store)
        assert invalid["failure_stage"] == "provenance"
        assert invalid["citation_valid"] == 0


def test_scorer_detects_cross_project_event_even_when_citation_scope_is_forged(benchmark, tmp_path):
    files, cases, responses, gold = benchmark
    q = IntelligentQuery.model_validate(cases[0]["queries"][0])
    foreign = Event(event_id="foreign", project_id="B", source_id="foreign-source", subject="project", predicate="database", value="MySQL", event_type="declare", observed_at="2026-01-01T00:00:00Z")
    other_path = write_jsonl(tmp_path / "other.jsonl", [foreign.model_dump(mode="json")])
    with SQLiteMemoryStore(tmp_path / "score.sqlite3") as store:
        store.import_jsonl(files["gold"])
        store.import_jsonl(other_path)
        forged = foreign.model_dump(mode="json")
        forged["project_id"] = "A"
        response = {"project_id": "A", "hits": [{"subject": "project", "predicate": "database", "result": {"status": "ok", "value": "MySQL", "evidence": [forged], "reason": "synthetic injection"}}]}
        score = score_search_response(q, response, store)
        assert not score["passed"]
        assert score["project_leakage"]
        assert score["leaked_event_ids"] == ["foreign"]


def test_scorer_rejects_wrong_status_and_valid_but_wrong_source_set(benchmark, tmp_path):
    files, cases, responses, gold = benchmark
    q = IntelligentQuery.model_validate(cases[0]["queries"][0])
    with SQLiteMemoryStore(tmp_path / "score.sqlite3") as store:
        store.import_jsonl(files["gold"])
        response = intelligent.HybridMemorySearch(store).search(q.project_id, q.text, q.as_of, mode="lexical", top_k=3)
        wrong_status = deepcopy(response)
        wrong_status["hits"][0]["result"] = {"status": "unknown", "value": None, "evidence": [], "reason": "synthetic incorrect refusal"}
        assert score_search_response(q, wrong_status, store)["failure_stage"] == "resolution"
        older = Event(event_id="same-value-older", project_id="A", source_id="different-source", subject="project", predicate="database", value="MySQL", event_type="declare", observed_at="2026-02-01T00:00:00Z")
        store.import_jsonl(write_jsonl(tmp_path / "older.jsonl", [older.model_dump(mode="json")]))
        wrong_sources = deepcopy(response)
        wrong_sources["hits"][0]["result"]["evidence"] = [older.model_dump(mode="json")]
        score = score_search_response(q, wrong_sources, store)
        assert score["citation_valid"] == score["citation_total"] == 1
        assert score["answer_correct"]
        assert not score["sources_correct"]
        assert score["failure_stage"] == "provenance"


def test_unknown_only_zero_denominators_are_not_fabricated_as_100_percent(benchmark, tmp_path):
    files, cases, responses, gold = benchmark
    write_jsonl(files["dataset"], [cases[2]])
    write_jsonl(files["responses"], [responses[2]])
    report = run(files, tmp_path / "unknown.md")
    assert report["metrics"]["all_passed"]
    assert report["metrics"]["extraction"]["precision"] is None
    assert report["metrics"]["extraction"]["recall"] is None
    assert report["metrics"]["retrieval"]["recall_at_3"] is None
    assert report["metrics"]["end_to_end"]["unknown_expected_count"] == 1
    assert report["metrics"]["end_to_end"]["unknown_information_handling_rate"] == 1
    assert report["metrics"]["source_validity"] is None
    assert not report["metrics"]["release_gate_passed"]


def test_invalid_live_config_and_offline_vectors_fail_before_network(benchmark, tmp_path, monkeypatch):
    files, cases, responses, gold = benchmark
    monkeypatch.setattr(intelligent.ProviderConfig, "from_env", lambda: ProviderConfig(chat_model="test", api_key=None))
    with pytest.raises(ValueError, match="configured chat API key"):
        run(files, tmp_path / "live.md", live=True)
    with pytest.raises(ValueError, match="recorded vectors_path"):
        run(files, tmp_path / "offline-hybrid.md", search_mode="hybrid")
    with pytest.raises(ValueError, match="responses_path"):
        run_intelligent_evaluation(files["seeds"], files["gold"], files["dataset"], tmp_path / "no-replay.md", responses_path=None)


def test_missing_live_embedding_configuration_fails_before_any_chat_request(benchmark, tmp_path, monkeypatch):
    files, cases, responses, gold = benchmark
    monkeypatch.setattr(intelligent.ProviderConfig, "from_env", lambda: ProviderConfig(chat_model="local-test", api_key="not-a-real-key"))
    def not_configured():
        raise ValueError("synthetic embedding key missing")
    monkeypatch.setitem(sys.modules, "repomind.intelligence.dashscope", SimpleNamespace(embedding_provider_from_env=not_configured))
    def forbidden(*args, **kwargs):
        pytest.fail("chat request occurred before embedding config validation")
    monkeypatch.setattr(intelligent.OpenAICompatibleProvider, "extract", forbidden)
    with pytest.raises(ValueError, match="embedding key missing"):
        run(files, tmp_path / "live-hybrid.md", live=True, search_mode="hybrid")


def test_live_lexical_branch_is_explicitly_partial_using_local_stub_only(benchmark, tmp_path, monkeypatch):
    files, cases, responses, gold = benchmark
    recorded = intelligent.ReplayExtractionProvider(files["responses"])
    monkeypatch.setattr(intelligent.ProviderConfig, "from_env", lambda: ProviderConfig(chat_model="local-stub-test", api_key="not-a-real-key"))
    class LocalLiveBranchStub:
        name = "local-test-double-for-live-control-flow"
        def __init__(self, config):
            pass
        def extract(self, source, context):
            return recorded.extract(source, context)
        def safe_metadata(self):
            return {"name": self.name, "test_only": True}
    monkeypatch.setattr(intelligent, "OpenAICompatibleProvider", LocalLiveBranchStub)
    report = run(files, tmp_path / "stub-live.md", live=True)
    assert report["validation"]["live_extraction"]
    assert not report["validation"]["real_semantic_quality"]
    assert report["validation"]["status"] == "partial"
    assert report["config"]["extraction_provider"]["test_only"]


@pytest.mark.parametrize("change,needle", [
    ({"case_id": ""}, "case_id"),
    ({"unexpected": "field"}, "unexpected"),
    ({"queries": []}, "queries"),
])
def test_case_validation_is_diagnosable(benchmark, tmp_path, change, needle):
    files, cases, responses, gold = benchmark
    cases[0].update(change)
    path = write_jsonl(tmp_path / "invalid.jsonl", [cases[0]])
    with pytest.raises(ValueError, match=needle) as raised:
        load_intelligent_cases(path)
    assert f"{path}:1:" in str(raised.value)


def test_duplicate_case_id_and_implicit_gold_time_are_rejected(benchmark, tmp_path):
    files, cases, responses, gold = benchmark
    path = write_jsonl(tmp_path / "duplicate.jsonl", [cases[0], cases[0]])
    with pytest.raises(ValueError, match="duplicate case_id"):
        load_intelligent_cases(path)
    cases[0]["expected_facts"][0]["effective_at"] = None
    with pytest.raises(ValueError, match="explicit effective_at"):
        load_intelligent_cases(write_jsonl(tmp_path / "implicit.jsonl", [cases[0]]))


def test_output_protection_and_bad_modes_are_validated(benchmark, tmp_path):
    files, cases, responses, gold = benchmark
    with pytest.raises(ValueError, match="must end"):
        run(files, tmp_path / "result.txt")
    with pytest.raises(ValueError, match="search_mode"):
        run(files, tmp_path / "result.md", search_mode="invalid")
    protected = tmp_path / "input.json"
    protected.write_bytes(files["dataset"].read_bytes())
    files["dataset"] = protected
    with pytest.raises(ValueError, match="must not overwrite"):
        run(files, protected)
