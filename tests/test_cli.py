import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args, cwd):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run([sys.executable, "-m", "repomind", *map(str, args)], cwd=cwd,
                          env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)


def test_separate_process_persistence_idempotence_and_temporal_queries(tmp_path):
    events = ROOT / "data/fixtures/conversations.jsonl"
    db = tmp_path / "memory.sqlite3"
    first = run_cli("--db", db, "import", events, cwd=tmp_path)
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["imported"] == 60
    again = run_cli("import", events, "--db", db, cwd=tmp_path)
    assert json.loads(again.stdout)["duplicates"] == 60
    for cutoff, expected in [("2026-02-01", "MySQL"), ("2026-03-15", "MySQL"),
                             ("2026-04-10", "PostgreSQL")]:
        response = run_cli("query", "--db", db, "--project", "CampusRecruit", "--field", "database",
                           "--as-of", cutoff, cwd=tmp_path)
        assert response.returncode == 0, response.stderr
        result = json.loads(response.stdout)
        assert result["status"] == "ok" and result["value"] == expected
        assert all(e["project_id"] == "CampusRecruit" and e["source_id"] for e in result["evidence"])
    unknown = run_cli("query", "--db", db, "--project", "unseen", "--field", "database",
                      "--as-of", "2026-04-10", cwd=tmp_path)
    assert json.loads(unknown.stdout)["status"] == "unknown"


@pytest.mark.parametrize("args", [("--help",), ("query", "--help"), ("import", "--help"),
                                   ("eval", "--help"), ("--version",)])
def test_help_and_version(args, tmp_path):
    response = run_cli(*args, cwd=tmp_path)
    assert response.returncode == 0 and response.stdout


def test_missing_db_and_bad_time_have_nonzero_json_error(tmp_path):
    args = ("query", "--project", "A", "--field", "database", "--as-of")
    missing = run_cli(*args, "2026-01-01", cwd=tmp_path)
    assert missing.returncode == 2
    assert json.loads(missing.stderr)["error"] == "FileNotFoundError"
    invalid = run_cli(*args, "2026-01-01T00:00:00", cwd=tmp_path)
    assert invalid.returncode == 2
    assert "timezone" in json.loads(invalid.stderr)["message"]
    assert not (tmp_path / "repomind.sqlite3").exists()


def test_invalid_import_reports_line_and_nonzero_exit(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text("\n{bad}", encoding="utf-8")
    response = run_cli("import", path, cwd=tmp_path)
    assert response.returncode == 2
    assert "bad.jsonl:2" in json.loads(response.stderr)["message"]


def test_eval_cli_reports_and_exit_codes(tmp_path):
    source = ROOT / "data/dev/questions.jsonl"
    data = tmp_path / "one-question.jsonl"
    question = json.loads(source.read_text(encoding="utf-8").splitlines()[0])
    data.write_text(json.dumps(question), encoding="utf-8")
    args = ("eval", "--events", ROOT / "data/fixtures/conversations.jsonl", "--dataset", data,
            "--output", tmp_path / "evaluation.md")
    response = run_cli(*args, cwd=tmp_path)
    assert response.returncode == 0, response.stderr
    assert json.loads(response.stdout)["metrics"]["correct"] == 1
    assert (tmp_path / "evaluation.json").exists() and (tmp_path / "evaluation.md").exists()
    assert not (tmp_path / "repomind.sqlite3").exists()
    question["expected"][0]["value"] = "intentionally incorrect gold for exit-code test"
    data.write_text(json.dumps(question), encoding="utf-8")
    failed = run_cli(*args, cwd=tmp_path)
    assert failed.returncode == 1
    assert json.loads(failed.stdout)["metrics"]["correct"] == 0
