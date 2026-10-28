import importlib.util
import json
from pathlib import Path

import pytest

from repomind.comparison import runner
from repomind.comparison.base import ScopeViolationError
from repomind.platform.tracing import TraceOutbox

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/v1.2"


def run(tmp_path, **kwargs):
    return runner.run_comparison(DATA / "events.jsonl", DATA / "dev/questions.jsonl", tmp_path / "result.json",
        vectors_path=DATA / "recorded-vectors.json", state_dir=tmp_path / "state", run_id="test-dev", **kwargs)


def test_recorded_native_negative_control_and_trace_roundtrip(tmp_path):
    report = run(tmp_path, variants=["no_memory", "repomind_semantic", "repomind_hybrid"])
    assert report["validation"]["completed_without_errors"]
    assert report["config"]["synthetic"] is True
    assert report["variants"]["no_memory"]["metrics"]["correct"] == 2
    assert report["variants"]["repomind_semantic"]["metrics"]["correct"] == 12
    assert report["variants"]["repomind_hybrid"]["metrics"]["correct"] == 12
    assert report["vector_parity"]["input_set_parity"]
    assert report["vector_parity"]["vector_digest_parity"]
    traces = TraceOutbox(report["outbox"]).records()
    assert len(traces) == 36 and all(trace.synthetic for trace in traces)
    assert all("expected_key" not in trace.input for trace in traces)
    assert all(trace.expected_output is not None for trace in traces)
    assert all(variant["pricing"]["amount"] is None for variant in report["variants"].values())
    assert (tmp_path / "result.md").read_text(encoding="utf-8").startswith("# 阶段目标")
    assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8")) == report
    assert report["timings"]["report_serialization_and_write_seconds"] >= 0


@pytest.mark.skipif(importlib.util.find_spec("mem0") is None, reason="optional Mem0 SDK not installed")
def test_real_mem0_same_vectors_dev_comparison(tmp_path):
    report = run(tmp_path)
    assert report["validation"]["completed_without_errors"]
    assert report["variants"]["mem0"]["metrics"]["correct"] == 12
    assert report["vector_parity"]["input_set_parity"]
    assert report["vector_parity"]["vector_digest_parity"]
    assert report["variants"]["mem0"]["metadata"]["scope_violation_count"] == 0
    assert report["variants"]["mem0"]["metadata"]["embedding"]["request_count"] == 0


def test_provider_only_receives_scope_and_query_not_gold(tmp_path, monkeypatch):
    calls = []

    class Probe:
        def index(self, project_id, known_at=None):
            calls.append(("index", project_id, known_at))
            return {}

        def search(self, project_id, text, as_of, known_at=None, top_k=3, min_cosine=.55):
            calls.append(("search", project_id, text, as_of, known_at, top_k, min_cosine))
            return {"project_id": project_id, "hits": []}

        def safe_metadata(self):
            return {"name": "probe", "embedding": None}

        def close(self):
            calls.append(("close",))

    monkeypatch.setattr(runner, "_make_provider", lambda *args: Probe())
    report = run(tmp_path, variants=["no_memory"])
    assert report["validation"]["completed_without_errors"]
    assert len([call for call in calls if call[0] == "search"]) == 12
    assert calls[-1] == ("close",)


def test_scope_guard_error_is_reported_as_leakage_not_success(tmp_path, monkeypatch):
    class Broken:
        def index(self, *args, **kwargs):
            raise ScopeViolationError("blocked wrong-scope read")

        def safe_metadata(self):
            return {"name": "broken", "embedding": None}

        def close(self):
            pass

    monkeypatch.setattr(runner, "_make_provider", lambda *args: Broken())
    report = run(tmp_path, variants=["no_memory"])
    assert not report["validation"]["completed_without_errors"]
    assert report["variants"]["no_memory"]["metrics"]["project_leakage_count"] == 12
    assert report["variants"]["no_memory"]["metrics"]["infrastructure_error_count"] == 12
    assert all(failure["error_phase"] == "index" for failure in report["failures"])


def test_existing_evidence_is_never_overwritten(tmp_path, monkeypatch):
    run(tmp_path, variants=["no_memory"])
    before = (tmp_path / "result.json").read_bytes()
    monkeypatch.setattr(runner, "_make_provider", lambda *args: pytest.fail("provider must not be constructed"))
    with pytest.raises(ValueError, match="already exists"):
        run(tmp_path, variants=["no_memory"])
    assert (tmp_path / "result.json").read_bytes() == before


def test_modified_frozen_input_rejected_before_calls(tmp_path, monkeypatch):
    import shutil
    copied = tmp_path / "data"
    shutil.copytree(DATA, copied)
    with (copied / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("\n")
    monkeypatch.setattr(runner, "_make_provider", lambda *args: pytest.fail("provider must not be constructed"))
    with pytest.raises(ValueError, match="frozen manifest"):
        runner.run_comparison(copied / "events.jsonl", copied / "dev/questions.jsonl", tmp_path / "out.json",
            vectors_path=copied / "recorded-vectors.json", state_dir=tmp_path / "state")


@pytest.mark.parametrize("run_id", ["../escape", "..", "x/y", "C:\\other", "a" * 81])
def test_run_id_cannot_escape_isolated_directory(tmp_path, run_id):
    with pytest.raises(ValueError, match="filename-safe"):
        runner.run_comparison(DATA / "events.jsonl", DATA / "dev/questions.jsonl", tmp_path / "out.json",
            vectors_path=DATA / "recorded-vectors.json", run_id=run_id)


def test_no_manifest_stays_local_and_cannot_be_exported_as_synthetic(tmp_path):
    import shutil
    directory = tmp_path / "untrusted"
    directory.mkdir()
    for path in (DATA / "events.jsonl", DATA / "dev/questions.jsonl", DATA / "recorded-vectors.json"):
        shutil.copy(path, directory / path.name)
    report = runner.run_comparison(directory / "events.jsonl", directory / "questions.jsonl", tmp_path / "out.json",
        vectors_path=directory / "recorded-vectors.json", variants=["no_memory"], state_dir=tmp_path / "state")
    assert not report["config"]["synthetic"]
    assert all(not trace.synthetic for trace in TraceOutbox(report["outbox"]).records())


def test_output_cannot_corrupt_provider_runtime_database(tmp_path):
    with pytest.raises(ValueError, match="runtime directories"):
        run(tmp_path, variants=["no_memory"], outbox_path=tmp_path / "state/test-dev/no_memory/ledger.sqlite3")
    assert not (tmp_path / "state/test-dev").exists()


def test_provider_close_failure_retains_report_and_marks_run_incomplete(tmp_path, monkeypatch):
    from repomind.comparison.providers import NoMemoryProvider

    class CloseFailure(NoMemoryProvider):
        def close(self):
            raise OSError("close failed")

    monkeypatch.setattr(runner, "_make_provider", lambda *args: CloseFailure())
    report = run(tmp_path, variants=["no_memory"])
    assert not report["validation"]["completed_without_errors"]
    assert report["variants"]["no_memory"]["cleanup_errors"] == [{"component": "memory_provider", "error_type": "OSError"}]
    assert (tmp_path / "result.json").is_file()
