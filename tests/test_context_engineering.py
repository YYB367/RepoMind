import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from repomind.cli import main
from repomind.context.benchmark import _load_inputs, _score, Answer, run_benchmark
from repomind.context.openviking import OpenVikingReader
from repomind.context.selection import Corpus, ContextSelector, evidence_json

ROOT = Path(__file__).resolve().parents[1] / "data/v2.1"


def test_layered_scope_and_exact_multibyte_budget(tmp_path):
    source = {
        "projects": {
            "left": [{"id": "docs", "abstract": "部署", "overview": "readiness | 部署检查",
                      "documents": [{"id": "readiness", "title": "部署检查", "body": "路径是 /readyz"}]}],
            "right": [{"id": "docs", "abstract": "部署", "overview": "readiness | 部署检查",
                       "documents": [{"id": "readiness", "title": "部署检查", "body": "路径是 /secret"}]}],
        }
    }
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    selector = ContextSelector(Corpus.load(path))
    expected = [{"source_id": "readiness", "text": "路径是 /readyz"}]
    size = len(evidence_json(expected).encode("utf-8"))
    exact = selector.select("left", "部署检查", "layered", size)
    smaller = selector.select("left", "部署检查", "layered", size - 1)
    assert exact["evidence"] == expected and exact["evidence_bytes"] == size
    assert [visit["level"] for visit in exact["visits"]] == ["L0", "L1", "L2"]
    assert smaller["evidence"] == [] and smaller["evidence_bytes"] == 2
    assert [visit["level"] for visit in smaller["visits"]] == ["L0", "L1"]


def test_openviking_scoped_uri_routes_and_errors(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def read(self, limit):
            return self.payload

    class Opener:
        calls = []
        payload = b'{"status":"ok","result":"Read from server"}'

        def open(self, request, *, timeout):
            parsed = urlsplit(request.full_url)
            self.calls.append((parsed.path, parse_qs(parsed.query)["uri"][0],
                               request.get_header("Authorization"), timeout))
            response = Response()
            response.payload = self.payload
            return response

    reader = OpenVikingReader("http://127.0.0.1:1933", "viking://resources/bench", "test-key")
    stub = Opener()
    monkeypatch.setattr(reader, "_opener", stub)
    for level, name, doc in (("L0", "abstract", None), ("L1", "overview", None), ("L2", "read", "probe")):
        assert reader(level, "cedar-api", "runtime", doc) == "Read from server"
        assert stub.calls[-1] == (
            "/api/v1/content/" + name, "viking://resources/bench/cedar-api/runtime" + ("/probe.md" if doc else ""),
            "Bearer test-key", 15,
        )
    with pytest.raises(ValueError, match="invalid OpenViking"):
        reader("L2", "../other", "runtime", "probe")
    stub.payload = b'{"status":"error","result":"sensitive upstream details"}'
    with pytest.raises(ValueError, match="did not return text for L1") as error:
        reader("L1", "cedar-api", "runtime", None)
    assert "sensitive" not in str(error.value)
    assert len(stub.calls) == 4


def test_benchmark_pairs_budgets_and_does_not_treat_offline_as_answer_quality():
    report = run_benchmark(ROOT, "dev", (640, 1800))
    assert report["mode"] == "offline-retrieval-only" and report["model_requests"] == 0
    assert len(report["trials"]) == 12
    assert len({(row["question_id"], row["strategy"], row["budget_bytes"]) for row in report["trials"]}) == 12
    assert all(row["evidence_bytes"] <= row["budget_bytes"] for row in report["trials"])
    assert all(row["exact_with_citations"] is None and row["input_tokens"] is None for row in report["summary"])
    _, questions, _ = _load_inputs(ROOT, "holdout")
    item = next(question for question in questions if question.id == "hold-07")
    assert not _score(item, item.gold, {"canary"})
    assert _score(item, item.gold, {"canary", "build-gate", "rollback"})
    assert not _score(item, Answer(answer=item.gold.answer, citations=("canary",)), {"canary", "build-gate"})


def test_benchmark_rejects_changed_frozen_data_and_existing_output(tmp_path, capsys):
    for name in ("corpus.json", "dev.jsonl", "holdout.jsonl", "manifest.json"):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    (tmp_path / "holdout.jsonl").write_bytes(b"\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        run_benchmark(tmp_path, "dev", (640,))
    output = tmp_path / "existing.json"
    output.write_text("keep", encoding="utf-8")
    assert main(["context-bench", "--data-root", str(ROOT), "--output", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == "keep"
    assert main(["context-select", "--corpus", str(ROOT / "corpus.json"), "--project", "pine-api",
                 "--query", "backup retention", "--budget", "640"]) == 0
    assert json.loads(capsys.readouterr().out)["evidence"][0]["source_id"] == "backup"
