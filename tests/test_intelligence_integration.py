"""Independent V1.1 integration checks using only temporary synthetic sources.

Never load the project .env, held-out questions, or real service credentials.
Subprocesses receive an explicit environment allowlist, not the parent secrets.
"""

import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.cli import main
from repomind.domain.models import Event, MemoryQuery
from repomind.intelligence.config import configuration_status, load_env_file
from repomind.intelligence.extraction import Extractor
from repomind.intelligence.ingestion import prepare_ingestion, read_sources
from repomind.intelligence.models import ExtractionBatch, SourceMessage
from repomind.memory.retriever import MemoryRetriever
from repomind.memory.store import ImportValidationError


ROOT = Path(__file__).resolve().parents[1]
_CONFIG_NAMES = {
    "REPOMIND_PROVIDER", "REPOMIND_API_KEY", "REPOMIND_BASE_URL", "REPOMIND_CHAT_MODEL",
    "REPOMIND_CHAT_FORMAT", "REPOMIND_TIMEOUT_SECONDS", "REPOMIND_MAX_COMPLETION_TOKENS",
    "REPOMIND_EMBEDDING_BASE_URL", "REPOMIND_EMBEDDING_API_KEY", "REPOMIND_EMBEDDING_MODEL",
    "REPOMIND_LITERAL_DEMO", "OPENAI_API_KEY", "OPENAI_BASE_URL", "DEEPSEEK_API_KEY",
}


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    names = _CONFIG_NAMES | {name for name in os.environ if name.startswith(("REPOMIND_", "OPENAI_", "DEEPSEEK_"))}
    for name in names:
        # Register absent names as well, so dotenv writes are undone after tests.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def source(*, project="IntegrationA", source_id="conversation-1", text="We use MySQL.",
           observed="2026-07-01T00:00:00Z"):
    return SourceMessage(project_id=project, source_id=source_id, text=text, observed_at=observed)


def batch(value="MySQL", *, quote="We use MySQL.", kind="declare", target=None):
    return ExtractionBatch.model_validate({"facts": [{
        "subject": "project", "predicate": "database", "value": value,
        "event_type": kind, "effective_at": None, "supersedes_event_id": target,
        "evidence_text": quote,
    }], "abstain_reason": None})


class SyntheticProvider:
    name = "integration-synthetic-replay-not-live"

    def __init__(self, response):
        self.response = response

    def extract(self, envelope, context):
        return self.response


def memory(envelope=None, response=None):
    return Extractor(SyntheticProvider(response or batch())).extract(envelope or source())


def snapshot(store):
    return {table: [tuple(row) for row in store.connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
            for table in ("events", "nl_sources", "extraction_provenance", "memory_vectors")}


def write_replay(tmp_path, envelopes=None, responses=None):
    envelopes = envelopes or [source()]
    responses = responses or [batch()]
    sources_path, responses_path = tmp_path / "sources.jsonl", tmp_path / "responses.jsonl"
    sources_path.write_text("".join(item.model_dump_json() + "\n" for item in envelopes), encoding="utf-8")
    responses_path.write_text("".join(json.dumps({"source_sha256": item.content_hash,
                                                 "response": response.model_dump(mode="json")}) + "\n"
                                      for item, response in zip(envelopes, responses)), encoding="utf-8")
    return sources_path, responses_path


def run_cli(tmp_path, *arguments, extra_env=None):
    names = ("SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT")
    environment = {name: os.environ[name] for name in names if name in os.environ}
    environment.update({"PYTHONPATH": str(ROOT / "src"), "PYTHONUTF8": "1"})
    environment.update(extra_env or {})
    return subprocess.run([sys.executable, "-m", "repomind", *map(str, arguments)],
                          cwd=tmp_path, env=environment, capture_output=True,
                          text=True, encoding="utf-8", timeout=30)


def test_schema_one_upgrade_retains_every_event_and_raw_byte_string(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    old_event = Event(event_id="legacy", project_id="IntegrationA", source_id="旧会话",
                      subject="project", predicate="database", value="MySQL", event_type="declare",
                      observed_at="2026-01-01T00:00:00Z")
    raw = "  " + json.dumps(old_event.model_dump(mode="json"), ensure_ascii=False, indent=2) + "  "
    canonical = SQLiteMemoryStore._canonical(old_event)
    data = old_event.model_dump(mode="json")
    columns = ("event_id", "project_id", "subject", "predicate", "value", "event_type",
               "observed_at", "effective_at", "source_id", "supersedes_event_id")
    with sqlite3.connect(path) as database:
        database.execute("""CREATE TABLE events (
            event_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, subject TEXT NOT NULL,
            predicate TEXT NOT NULL, value TEXT NOT NULL, event_type TEXT NOT NULL,
            observed_at TEXT NOT NULL, effective_at TEXT NOT NULL, source_id TEXT NOT NULL,
            supersedes_event_id TEXT, canonical_json TEXT NOT NULL, raw_json TEXT NOT NULL)""")
        database.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         tuple(data[column] for column in columns) + (canonical, raw))
        database.execute("PRAGMA user_version=1")
        before = database.execute("SELECT * FROM events").fetchall()
    with SQLiteMemoryStore(path) as upgraded:
        assert upgraded.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert [tuple(row) for row in upgraded.connection.execute("SELECT * FROM events")] == before
        assert upgraded.connection.execute("SELECT raw_json FROM events").fetchone()[0] == raw
        assert upgraded.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert snapshot(upgraded)["nl_sources"] == []
        answer = MemoryRetriever(upgraded).query(MemoryQuery(
            project_id="IntegrationA", predicate="database", as_of="2026-02-01"))
        assert answer.value == "MySQL"


def test_unknown_schema_keeps_version_objects_content_and_file_unchanged(tmp_path):
    path = tmp_path / "future.sqlite3"
    with sqlite3.connect(path) as database:
        database.execute("CREATE TABLE future_content (value TEXT)")
        database.execute("INSERT INTO future_content VALUES ('keep me')")
        database.execute("PRAGMA user_version=999")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="unsupported database schema version 999"):
        SQLiteMemoryStore(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    with sqlite3.connect(path) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 999
        assert database.execute("SELECT value FROM future_content").fetchall() == [("keep me",)]
        assert database.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [("future_content",)]


def test_source_event_and_quote_commit_survive_restart_and_repeat_idempotently(tmp_path):
    path, extracted = tmp_path / "memory.db", memory()
    with SQLiteMemoryStore(path) as store:
        assert store.import_extractions([extracted]).imported == 1
        before = snapshot(store)
    with SQLiteMemoryStore(path) as restarted:
        result = restarted.import_extractions([extracted])
        assert (result.imported, result.duplicates) == (0, 1)
        assert snapshot(restarted) == before
        envelope = restarted.get_source("IntegrationA", "conversation-1")
        provenance = restarted.get_provenance(extracted.events[0].event_id)
        assert envelope["text"] == "We use MySQL."
        assert provenance["evidence_text"] == "We use MySQL."
        assert provenance["provider"] == "integration-synthetic-replay-not-live"


def test_late_batch_bad_quote_rolls_back_sources_events_and_provenance(tmp_path):
    first = memory()
    second = memory(source(source_id="conversation-2", text="We use PostgreSQL."),
                    batch("PostgreSQL", quote="We use PostgreSQL."))
    forged = second.model_copy(update={"evidence_by_event": {second.events[0].event_id: "not in source"}})
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        before = snapshot(store)
        with pytest.raises(ImportValidationError, match="quote"):
            store.import_extractions([first, forged])
        assert snapshot(store) == before
        assert store.import_extractions([first, second]).imported == 2


def test_reused_source_identifier_with_different_text_rolls_back_new_event(tmp_path):
    first = memory()
    changed = memory(source(text="We use PostgreSQL."), batch("PostgreSQL", quote="We use PostgreSQL."))
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        store.import_extractions([first])
        before = snapshot(store)
        with pytest.raises(ImportValidationError, match="different source content"):
            store.import_extractions([changed])
        assert snapshot(store) == before


def test_same_source_identifier_is_independent_between_projects(tmp_path):
    first = memory()
    second = memory(source(project="IntegrationB", text="We use PostgreSQL."),
                    batch("PostgreSQL", quote="We use PostgreSQL."))
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        assert store.import_extractions([first, second]).imported == 2
        assert store.get_source("IntegrationA", "conversation-1")["text"] == "We use MySQL."
        assert store.get_source("IntegrationB", "conversation-1")["text"] == "We use PostgreSQL."
        assert store.get_provenance(second.events[0].event_id)["project_id"] == "IntegrationB"


def test_store_rejects_event_outside_source_envelope_atomically(tmp_path):
    extracted = memory()
    forged_event = extracted.events[0].model_copy(update={"project_id": "IntegrationB"})
    forged = extracted.model_copy(update={"events": [forged_event]})
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        with pytest.raises(ImportValidationError, match="envelope"):
            store.import_extractions([forged])
        assert all(not rows for rows in snapshot(store).values())


def test_store_rejects_observation_time_outside_source_envelope(tmp_path):
    extracted = memory()
    later_event = extracted.events[0].model_copy(update={
        "observed_at": SourceMessage(project_id="A", source_id="t", text="clock",
                                     observed_at="2026-08-01T00:00:00Z").observed_at,
    })
    forged = extracted.model_copy(update={"events": [later_event]})
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        with pytest.raises(ValueError, match="envelope|source|observation|bound"):
            store.import_extractions([forged])
        assert all(not rows for rows in snapshot(store).values())


def test_existing_event_quote_cannot_be_silently_replaced(tmp_path):
    extracted = memory()
    alternate = extracted.model_copy(update={"evidence_by_event": {extracted.events[0].event_id: "MySQL"}})
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        store.import_extractions([extracted])
        before = snapshot(store)
        with pytest.raises(ImportValidationError, match="different extraction quote"):
            store.import_extractions([alternate])
        assert snapshot(store) == before


def test_explicit_abstention_source_can_be_audited_without_invented_events(tmp_path):
    envelope = source(text="Which database should we use?")
    refusal = ExtractionBatch(facts=[], abstain_reason="Question only; no adopted fact.")
    extracted = memory(envelope, refusal)
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        result = store.import_extractions([extracted])
        assert (result.imported, result.duplicates) == (0, 0)
        assert store.get_source("IntegrationA", "conversation-1")["text"] == envelope.text
        assert snapshot(store)["events"] == snapshot(store)["extraction_provenance"] == []


def test_prepare_batch_context_tracks_new_same_project_candidates_only(tmp_path):
    envelopes = [source(), source(source_id="conversation-2", text="Correction: PostgreSQL.",
                                observed="2026-07-02T00:00:00Z"),
                 source(project="IntegrationB", source_id="conversation-1", text="We use MySQL.")]

    class ContextProvider:
        name = "integration-context-test-double"

        def __init__(self):
            self.contexts = []

        def extract(self, envelope, context):
            self.contexts.append((envelope.project_id, [item.project_id for item in context]))
            if envelope.source_id == "conversation-2":
                assert len(context) == 1
                return batch("PostgreSQL", quote="Correction: PostgreSQL.", kind="correct", target=context[0].event_id)
            return batch()

    provider = ContextProvider()
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        prepared = prepare_ingestion(store, envelopes, provider)
        assert store.count() == 0
        assert prepared[1].events[0].supersedes_event_id == prepared[0].events[0].event_id
        assert provider.contexts == [("IntegrationA", []), ("IntegrationA", ["IntegrationA"]), ("IntegrationB", [])]
        assert store.import_extractions(prepared).imported == 3


@pytest.mark.parametrize("kind", ["duplicate-key", "conflicting-source"])
def test_source_reader_rejects_duplicate_keys_or_conflicting_source_at_line(tmp_path, kind):
    path = tmp_path / "invalid-sources.jsonl"
    valid = source().model_dump_json()
    invalid = ('{"project_id":"A","project_id":"B"}' if kind == "duplicate-key"
               else source(text="Different content.").model_dump_json())
    path.write_text(valid + "\n" + invalid + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid-sources.jsonl:2"):
        read_sources(path)


def test_cli_dry_run_writes_review_artifacts_without_creating_ledger(tmp_path):
    inputs, responses = write_replay(tmp_path)
    database, output = tmp_path / "not-created.db", tmp_path / "candidates.jsonl"
    response = run_cli(tmp_path, "--db", database, "ingest", inputs, "--provider", "replay",
                       "--responses", responses, "--output", output)
    assert response.returncode == 0, response.stderr
    receipt = json.loads(response.stdout)
    assert receipt["applied"] is False and receipt["import"] is None
    assert not database.exists()
    assert output.is_file() and output.with_suffix(".audit.json").is_file()
    audit = json.loads(output.with_suffix(".audit.json").read_text(encoding="utf-8"))
    assert audit["memories"][0]["source"]["text"] == "We use MySQL."
    assert list(audit["memories"][0]["evidence_by_event"].values()) == ["We use MySQL."]


def test_cli_dry_run_leaves_existing_event_and_provenance_tables_unchanged(tmp_path):
    database = tmp_path / "existing.db"
    with SQLiteMemoryStore(database) as store:
        store.import_extractions([memory()])
        before = snapshot(store)
    envelope = source(source_id="new-source", text="We use PostgreSQL.")
    inputs, responses = write_replay(tmp_path, [envelope], [batch("PostgreSQL", quote=envelope.text)])
    response = run_cli(tmp_path, "ingest", inputs, "--db", database, "--provider", "replay",
                       "--responses", responses, "--output", tmp_path / "review.jsonl")
    assert response.returncode == 0, response.stderr
    with SQLiteMemoryStore(database) as store:
        assert snapshot(store) == before


def test_cli_apply_then_new_process_source_query_and_keyless_lexical_search(tmp_path):
    inputs, responses = write_replay(tmp_path)
    database, output = tmp_path / "applied.db", tmp_path / "candidates.jsonl"
    applied = run_cli(tmp_path, "ingest", inputs, "--db", database, "--provider", "replay",
                      "--responses", responses, "--output", output, "--apply")
    assert applied.returncode == 0, applied.stderr
    assert json.loads(applied.stdout)["import"]["imported"] == 1
    inspected = run_cli(tmp_path, "source", "--db", database, "--project", "IntegrationA",
                        "--source-id", "conversation-1")
    assert inspected.returncode == 0, inspected.stderr
    inspected = json.loads(inspected.stdout)
    assert inspected["status"] == "ok" and inspected["source"]["text"] == "We use MySQL."
    assert inspected["provenance"][0]["evidence_text"] == "We use MySQL."
    lexical = run_cli(tmp_path, "search", "--db", database, "--project", "IntegrationA",
                      "--text", "database", "--as-of", "2026-07-10", "--mode", "lexical")
    assert lexical.returncode == 0, lexical.stderr
    assert json.loads(lexical.stdout)["hits"][0]["result"]["value"] == "MySQL"
    with SQLiteMemoryStore(database) as store:
        assert store.connection.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0] == 0


@pytest.mark.parametrize("target_kind", ["input", "replay", "database", "audit-collides-with-input"])
def test_cli_candidate_outputs_cannot_overwrite_inputs_replay_or_database(tmp_path, target_kind):
    inputs, responses = write_replay(tmp_path)
    database = tmp_path / "memory.db"
    with SQLiteMemoryStore(database) as store:
        ledger_before = snapshot(store)
    output = {"input": inputs, "replay": responses, "database": database,
              "audit-collides-with-input": tmp_path / "sources.jsonl"}[target_kind]
    if target_kind == "audit-collides-with-input":
        renamed = tmp_path / "sources.audit.json"
        inputs.rename(renamed)
        inputs = renamed
    before = {path: path.read_bytes() for path in (inputs, responses)}
    rejected = run_cli(tmp_path, "ingest", inputs, "--db", database, "--provider", "replay",
                       "--responses", responses, "--output", output, "--apply")
    assert rejected.returncode == 2
    assert "overwrite" in json.loads(rejected.stderr)["message"]
    assert all(path.read_bytes() == content for path, content in before.items())
    # Opening a SQLite connection may change its header counter. Compare ledger
    # contents and integrity, rather than treating that header as an overwrite.
    with SQLiteMemoryStore(database) as store:
        assert snapshot(store) == ledger_before
        assert store.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_config_command_has_no_network_and_never_displays_test_credentials(tmp_path, monkeypatch, capsys):
    fake_key, fake_embedding_key = "synthetic-chat-credential-only", "synthetic-embedding-credential-only"
    (tmp_path / ".env").write_text(
        f"REPOMIND_API_KEY={fake_key}\nREPOMIND_CHAT_MODEL=synthetic-chat-model\n"
        f"REPOMIND_EMBEDDING_BASE_URL=https://example.invalid/v1\n"
        f"REPOMIND_EMBEDDING_API_KEY={fake_embedding_key}\nREPOMIND_EMBEDDING_MODEL=synthetic-embedding-model\n",
        encoding="utf-8")

    def forbidden_network(*args, **kwargs):
        raise AssertionError("config must not make network requests")

    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    assert main(["config"]) == 0
    captured = capsys.readouterr()
    assert fake_key not in captured.out + captured.err
    assert fake_embedding_key not in captured.out + captured.err
    status = json.loads(captured.out)
    assert status["chat_api_key_configured"] is True
    assert status["embedding_configured"] is True
    assert status["network_called"] is False
    assert status["env_file"] == str(tmp_path / ".env")
    assert not (tmp_path / "repomind.sqlite3").exists()


def test_dotenv_is_literal_preserves_environment_and_does_not_execute_dollar_expression(tmp_path, monkeypatch):
    marker = tmp_path / "must-not-be-created.txt"
    literal = f"$([System.IO.File]::WriteAllText('{marker}', 'executed'))"
    (tmp_path / ".env").write_text(
        "\ufeff# temporary synthetic configuration\n"
        f'REPOMIND_LITERAL_DEMO="{literal}"\n'
        "REPOMIND_API_KEY='synthetic-key-with-#-literal'\n"
        "REPOMIND_CHAT_MODEL=file-model # comment\n", encoding="utf-8")
    monkeypatch.setenv("REPOMIND_CHAT_MODEL", "environment-model")
    loaded = load_env_file()
    assert "REPOMIND_LITERAL_DEMO" in loaded
    assert os.environ["REPOMIND_LITERAL_DEMO"] == literal
    assert os.environ["REPOMIND_API_KEY"] == "synthetic-key-with-#-literal"
    assert os.environ["REPOMIND_CHAT_MODEL"] == "environment-model"
    assert not marker.exists()
    assert configuration_status()["network_called"] is False
