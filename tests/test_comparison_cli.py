"""V1.2 CLI contracts with local runner/export doubles; no keys or cloud calls."""

import builtins
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import sys
from types import ModuleType

import pytest

from repomind.cli import main
from repomind.intelligence import config as local_config
from repomind.platform import langfuse as langfuse_adapter


@pytest.fixture(autouse=True)
def isolated_local_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    names = {name for name in os.environ if name.startswith(("LANGFUSE_", "REPOMIND_", "OPENAI_", "DEEPSEEK_"))}
    names.update({"LANGFUSE_BASE_URL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"})
    for name in names:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)

    def forbidden_network(*args, **kwargs):
        raise AssertionError("CLI contract tests must not make network requests")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect", forbidden_network)


def comparison_runner(monkeypatch, *, completed=True, error=None):
    calls = []
    module = ModuleType("repomind.comparison.runner")

    def run(events, dataset, output, **kwargs):
        calls.append((events, dataset, output, kwargs))
        if error:
            raise error
        return {"validation": {"completed_without_errors": completed}, "variants": {
            "no_memory": {"metrics": {"accuracy": 0.0}, "queries": ["not printed in summary"]},
            "repomind_hybrid": {"metrics": {"accuracy": 1.0}},
        }, "outbox": "local-outbox.jsonl"}

    module.run_comparison = run
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return calls


def test_compare_forwards_explicit_options_without_using_global_db(monkeypatch, capsys):
    calls = comparison_runner(monkeypatch)
    code = main(["--db", "unused.db", "compare", "--events", "events.jsonl", "--dataset", "questions.jsonl",
                 "--output", "reports/result.md", "--vector-mode", "recorded", "--vectors", "vectors.json",
                 "--variants", "no_memory", "repomind_hybrid", "--run-id", "run-123",
                 "--state-dir", "runtime", "--outbox", "runtime/outbox.jsonl", "--pricing", "price.json",
                 "--seed", "17", "--min-cosine", "0.61"])
    assert code == 0
    events, dataset, output, options = calls[0]
    assert (events, dataset, output) == (Path("events.jsonl"), Path("questions.jsonl"), Path("reports/result.md"))
    assert options == {"vector_mode": "recorded", "vectors_path": Path("vectors.json"),
                       "variants": ["no_memory", "repomind_hybrid"], "run_id": "run-123",
                       "state_dir": Path("runtime"), "outbox_path": Path("runtime/outbox.jsonl"),
                       "pricing_path": Path("price.json"), "seed": 17, "min_cosine": 0.61}
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["variants"]["no_memory"]["accuracy"] == 0
    assert "queries" not in receipt["variants"]["no_memory"]
    assert not Path("unused.db").exists()


def test_compare_defaults_do_not_load_credentials_or_reject_a_negative_control(monkeypatch, capsys):
    calls = comparison_runner(monkeypatch)
    monkeypatch.setattr(local_config, "load_env_file", lambda *args: pytest.fail("recorded CLI must not load .env"))
    assert main(["compare", "--dataset", "questions.jsonl", "--output", "result.json"]) == 0
    options = calls[0][3]
    assert calls[0][0] == Path("data/v1.2/events.jsonl")
    assert options["vectors_path"] == Path("data/v1.2/recorded-vectors.json")
    assert options["vector_mode"] == "recorded" and options["variants"] is None
    assert options["min_cosine"] == 0.55 and options["seed"] == 0
    assert json.loads(capsys.readouterr().out)["validation"]["completed_without_errors"] is True


def test_compare_live_configuration_is_left_to_runner_without_recorded_vectors(monkeypatch, capsys):
    calls = comparison_runner(monkeypatch)
    assert main(["compare", "--dataset", "questions.jsonl", "--output", "result.md", "--vector-mode", "live"]) == 0
    assert calls[0][3]["vector_mode"] == "live" and calls[0][3]["vectors_path"] is None


def test_compare_infrastructure_failure_returns_one_even_when_other_variant_is_accurate(monkeypatch, capsys):
    comparison_runner(monkeypatch, completed=False)
    assert main(["compare", "--dataset", "questions.jsonl", "--output", "result.md"]) == 1
    assert json.loads(capsys.readouterr().out)["validation"]["completed_without_errors"] is False


def test_compare_input_error_has_diagnostic_json_and_exit_two(monkeypatch, capsys):
    comparison_runner(monkeypatch, error=ValueError("run_id already exists"))
    assert main(["compare", "--dataset", "questions.jsonl", "--output", "result.md"]) == 2
    assert "run_id already exists" in json.loads(capsys.readouterr().err)["message"]


@pytest.mark.parametrize("extra", [["--variants", "mem0", "mem0"],
                                    ["--vector-mode", "live", "--vectors", "recorded.json"]])
def test_compare_rejects_ambiguous_variants_or_mixed_vector_modes_before_runner(monkeypatch, capsys, extra):
    calls = comparison_runner(monkeypatch)
    assert main(["compare", "--dataset", "questions.jsonl", "--output", "result.md", *extra]) == 2
    assert calls == []


def exporter_double(monkeypatch, *, traces=True, experiment=True, failure=None, close_failure=None):
    calls = []

    class Exporter:
        def __init__(self, settings):
            calls.append(("construct", settings.safe_metadata()))

        def sync(self, outbox):
            calls.append(("traces", outbox.path))
            if failure is not None:
                raise failure
            return {"cloud_verified": traces, "status": "verified" if traces else "partial"}

        def export_experiment(self, outbox, dataset_name, run_name=None):
            calls.append(("experiment", outbox.path, dataset_name, run_name))
            return {"cloud_verified": experiment, "status": "verified" if experiment else "partial"}

        def close(self):
            calls.append(("close",))
            if close_failure is not None:
                raise close_failure

    monkeypatch.setattr(langfuse_adapter, "LangfuseExporter", Exporter)
    return calls


def local_trace_inputs(tmp_path):
    outbox = tmp_path / "outbox.jsonl"
    outbox.write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "LANGFUSE_BASE_URL=https://unit-test.invalid\n"
        "LANGFUSE_PUBLIC_KEY=synthetic-public-test\n"
        "LANGFUSE_SECRET_KEY=synthetic-private-test\n", encoding="utf-8")
    return outbox


@pytest.mark.parametrize("mode,expected", [("traces", ["construct", "traces", "close"]),
                                            ("experiment", ["construct", "experiment", "close"]),
                                            ("both", ["construct", "traces", "experiment", "close"])])
def test_trace_sync_routes_only_requested_exports_and_persists_safe_receipt(tmp_path, monkeypatch, capsys, mode, expected):
    outbox = local_trace_inputs(tmp_path)
    calls = exporter_double(monkeypatch)
    path = tmp_path / "delivery.json"
    code = main(["trace-sync", mode, "--outbox", str(outbox), "--dataset-name", "synthetic-dataset",
                 "--run-name", "synthetic-run", "--receipt", str(path)])
    assert code == 0
    assert [item[0] for item in calls] == expected
    if mode in {"experiment", "both"}:
        assert next(item for item in calls if item[0] == "experiment")[2:] == ("synthetic-dataset", "synthetic-run")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    stdout = capsys.readouterr().out
    assert json.loads(stdout) == receipt
    assert receipt["cloud_verified"] is True
    assert receipt["model_executed_during_export"] is False
    assert "synthetic-private-test" not in stdout
    assert "synthetic-public-test" not in stdout


def test_trace_sync_defaults_to_trace_export_and_requires_readback_confirmation(tmp_path, monkeypatch, capsys):
    outbox = local_trace_inputs(tmp_path)
    calls = exporter_double(monkeypatch, traces=False)
    assert main(["trace-sync", "--outbox", str(outbox)]) == 1
    assert [item[0] for item in calls] == ["construct", "traces", "close"]
    assert json.loads(capsys.readouterr().out)["cloud_verified"] is False


def test_trace_sync_both_does_not_claim_success_if_only_traces_are_verified(tmp_path, monkeypatch, capsys):
    outbox = local_trace_inputs(tmp_path)
    exporter_double(monkeypatch, traces=True, experiment=False)
    assert main(["trace-sync", "both", "--outbox", str(outbox)]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["traces"]["cloud_verified"] is True
    assert result["experiment"]["cloud_verified"] is False


@pytest.mark.parametrize("target", ["outbox", "status", ".env", ".env.local"])
def test_trace_receipt_cannot_overwrite_inputs_status_or_configuration(tmp_path, monkeypatch, capsys, target):
    outbox = local_trace_inputs(tmp_path)
    status = Path(str(outbox) + ".status.jsonl")
    status.write_text("unchanged", encoding="utf-8")
    path = {"outbox": outbox, "status": status}.get(target, tmp_path / target)
    before = {name: name.read_bytes() for name in (outbox, status, tmp_path / ".env")}
    calls = exporter_double(monkeypatch)
    assert main(["trace-sync", "--outbox", str(outbox), "--receipt", str(path)]) == 2
    assert calls == []
    assert all(name.read_bytes() == content for name, content in before.items())
    assert "overwrite" in json.loads(capsys.readouterr().err)["message"]


def test_trace_sync_missing_or_torn_outbox_fails_before_loading_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(local_config, "load_env_file", lambda *args: pytest.fail("input must validate first"))
    path = tmp_path / "missing.jsonl"
    assert main(["trace-sync", "--outbox", str(path)]) == 2
    assert "does not exist" in capsys.readouterr().err
    path.write_text("{torn", encoding="utf-8")
    assert main(["trace-sync", "--outbox", str(path)]) == 2
    assert "invalid/torn" in capsys.readouterr().err


@pytest.mark.parametrize("kind", ["sync", "shutdown"])
def test_trace_sync_raw_upstream_errors_are_sanitized_and_exporter_closes(tmp_path, monkeypatch, capsys, kind):
    outbox = local_trace_inputs(tmp_path)
    error = RuntimeError("synthetic-sensitive-upstream-credential")
    calls = exporter_double(monkeypatch, failure=error if kind == "sync" else None,
                            close_failure=error if kind == "shutdown" else None)
    assert main(["trace-sync", "--outbox", str(outbox)]) == 2
    captured = capsys.readouterr()
    assert "synthetic-sensitive-upstream-credential" not in captured.out + captured.err
    assert "sensitive upstream" in captured.err
    assert calls[-1] == ("close",)


def test_config_reports_only_langfuse_presence_and_versions_without_importing_sdks(tmp_path, monkeypatch, capsys):
    local_trace_inputs(tmp_path)
    original_import = builtins.__import__
    imported = []

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in {"mem0", "langfuse", "qdrant_client", "openai"}:
            imported.append(name)
            raise AssertionError("config must inspect distribution metadata without importing SDKs")
        return original_import(name, *args, **kwargs)

    def version(name):
        if name == "openai":
            raise importlib.metadata.PackageNotFoundError(name)
        return {"mem0ai": "2.2.1", "qdrant-client": "1.20.0", "langfuse": "5.0.4"}[name]

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(importlib.metadata, "version", version)
    assert main(["config"]) == 0
    captured = capsys.readouterr()
    value = json.loads(captured.out)
    assert value["langfuse_base_url_configured"] is True
    assert value["langfuse_public_key_configured"] is True
    assert value["langfuse_secret_key_configured"] is True
    assert value["installed_versions"] == {"mem0ai": "2.2.1", "qdrant-client": "1.20.0", "openai": None, "langfuse": "5.0.4"}
    assert value["network_called"] is False and imported == []
    assert "synthetic-private-test" not in captured.out + captured.err
    assert "synthetic-public-test" not in captured.out + captured.err
    assert "https://unit-test.invalid" not in captured.out


@pytest.mark.parametrize("command", ["compare", "trace-sync"])
def test_new_commands_have_help_without_constructing_optional_providers(capsys, command):
    with pytest.raises(SystemExit) as raised:
        main([command, "--help"])
    assert raised.value.code == 0
    assert "--outbox" in capsys.readouterr().out
