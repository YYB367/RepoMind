"""Real Mem0 + embedded Qdrant contract tests using local synthetic vectors.

No .env, no question/gold files, no external model, no SDK telemetry or downloads.
"""

import importlib.util
import json
from pathlib import Path
import socket
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.comparison.base import ScopeViolationError
from repomind.comparison.mem0 import Mem0MemoryProvider, MemoryBackendError
from repomind.comparison.providers import NativeMemoryProvider
from repomind.domain.models import Event
from repomind.intelligence.search import SearchIndexError


pytestmark = pytest.mark.skipif(importlib.util.find_spec("mem0") is None,
                                reason="install the pinned optional comparison SDK to run real Mem0 contracts")


class SyntheticEmbeddings:
    fingerprint = "mem0-contract-synthetic-v1"
    dimension = 3

    def __init__(self):
        self.documents, self.queries = [], []
        self.fail_query = False
        self.fail_predicate = None
        self.config = SimpleNamespace(embedding_model="synthetic-local-vectors", embedding_dimensions=3)

    def embed(self, texts):
        self.documents.extend(texts)
        result = []
        for text in texts:
            predicate = json.loads(text)[1]
            if predicate == self.fail_predicate:
                raise ValueError("synthetic upstream failure must not leak")
            result.append({"database": [1.0, 0.0, 0.0], "workers": [0.0, 1.0, 0.0],
                           "deployment": [0.0, 0.0, 1.0]}[predicate])
        return result

    def embed_query(self, text):
        self.queries.append(text)
        if self.fail_query:
            raise ValueError("synthetic-sensitive-upstream-error")
        return {"where storage": [1.0, 0.0, 0.0], "workers": [0.0, 1.0, 0.0],
                "deployment": [0.0, 0.0, 1.0], "unrecorded": [-1.0, -1.0, -1.0]}[text]

    def safe_metadata(self):
        return {"fingerprint": self.fingerprint, "kind": "synthetic-test-double",
                "request_count": len(self.documents) + len(self.queries), "usage": {}}


def event(identifier, *, project="A", predicate="database", value="MySQL", kind="declare",
          observed="2026-01-01T00:00:00Z", effective=None, supersedes=None):
    return Event(event_id=identifier, project_id=project, subject="project", predicate=predicate,
                 value=value, event_type=kind, observed_at=observed, effective_at=effective,
                 source_id="source-" + identifier, supersedes_event_id=supersedes)


@pytest.fixture(autouse=True)
def no_external_network_or_user_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    home = tmp_path / "synthetic-home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    original_resolve = socket.getaddrinfo
    original_connect = socket.socket.connect
    external = []

    def resolve(host, *args, **kwargs):
        if host not in ("127.0.0.1", "localhost", "::1", b"127.0.0.1", b"localhost", None):
            external.append("DNS")
            raise AssertionError("Mem0 contract attempted non-loopback name resolution")
        return original_resolve(host, *args, **kwargs)

    def connect(connection, address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
            external.append("connect")
            raise AssertionError("Mem0 contract attempted non-loopback network")
        return original_connect(connection, address)

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(socket.socket, "connect", connect)
    yield
    assert external == []
    assert not (home / ".mem0").exists()


@pytest.fixture
def store(tmp_path):
    with SQLiteMemoryStore(tmp_path / "readout.db") as value:
        value.import_events([
            event("initial"),
            event("plan", kind="plan", value="PostgreSQL", observed="2026-02-01T00:00:00Z", effective="2026-04-01T00:00:00Z"),
            event("complete", kind="complete", value="PostgreSQL", observed="2026-04-02T00:00:00Z", effective="2026-04-01T00:00:00Z"),
            event("old-workers", predicate="workers", value="4"),
            event("correct-workers", predicate="workers", value="8", kind="correct", observed="2026-02-01T00:00:00Z",
                  effective="2026-01-01T00:00:00Z", supersedes="old-workers"),
            event("other-project", project="B", value="SQLite"),
        ])
        yield value


def make_provider(store, tmp_path, embedder=None, directory="mem0-state"):
    return Mem0MemoryProvider(store, embedder or SyntheticEmbeddings(), tmp_path / directory, "synthetic-run-1")


def test_real_sdk_raw_documents_search_and_shared_temporal_correction_readout(store, tmp_path):
    embedder = SyntheticEmbeddings()
    with make_provider(store, tmp_path, embedder) as provider:
        assert provider.safe_metadata()["bridge"] is None
        assert embedder.documents == embedder.queries == []
        assert provider.index("A")["requested"] == 2
        old = provider.search("A", "where\nstorage", "2026-03-01")["hits"][0]["result"]
        current = provider.search("A", "where storage", "2026-04-10")["hits"][0]["result"]
        corrected = provider.search("A", "workers", "2026-01-20")["hits"][0]["result"]
        assert old["value"] == "MySQL" and old["plan_event_ids"] == ["plan"]
        assert current["value"] == "PostgreSQL"
        assert corrected["value"] == "8"
        assert [item["event_id"] for item in corrected["evidence"]] == ["correct-workers"]
        metadata = provider.safe_metadata()
        assert metadata["bridge"]["llm_attempts"] == 0
        assert metadata["bridge"]["embedding_requests"] == 5
        assert metadata["telemetry"] is False
        assert metadata["scope_violation_count"] == 0
        assert embedder.queries == ["where storage", "where storage", "workers"]
        assert (tmp_path / "mem0-state" / "history.sqlite3").is_file()


def test_mem0_and_native_receive_identical_property_documents_and_query_texts(store, tmp_path):
    mem0_vectors, native_vectors = SyntheticEmbeddings(), SyntheticEmbeddings()
    native = NativeMemoryProvider(store, native_vectors, mode="semantic")
    native.index("A")
    expected = native.search("A", "where\nstorage", "2026-04-10")
    with make_provider(store, tmp_path, mem0_vectors) as provider:
        provider.index("A")
        actual = provider.search("A", "where\nstorage", "2026-04-10")
        assert actual["hits"][0]["result"] == expected["hits"][0]["result"]
    assert sorted(mem0_vectors.documents) == sorted(native_vectors.documents)
    assert mem0_vectors.queries == native_vectors.queries


def test_known_at_documents_and_sdk_run_filters_keep_future_observations_out(store, tmp_path):
    embedder = SyntheticEmbeddings()
    with make_provider(store, tmp_path, embedder) as provider:
        full = provider.index("A")
        with pytest.raises(SearchIndexError, match="reindex"):
            provider.search("A", "where storage", "2026-04-10", known_at="2026-01-20")
        assert embedder.queries == []
        old_start = len(embedder.documents)
        old = provider.index("A", known_at="2026-01-20")
        assert full["snapshot_id"] != old["snapshot_id"]
        assert all("PostgreSQL" not in text for text in embedder.documents[old_start:])
        result = provider.search("A", "where storage", "2026-04-10", known_at="2026-01-20")
        assert result["hits"][0]["result"]["value"] == "MySQL"
        assert result["hits"][0]["result"]["considered_event_ids"] == ["initial"]


def test_stale_scope_requires_explicit_reindex_without_silent_embedding(store, tmp_path):
    embedder = SyntheticEmbeddings()
    with make_provider(store, tmp_path, embedder) as provider:
        provider.index("A")
        store.import_events([event("new-state", value="DuckDB", observed="2026-05-01T00:00:00Z")])
        with pytest.raises(SearchIndexError, match="stale"):
            provider.search("A", "where storage", "2026-06-01")
        assert embedder.queries == []
        provider.index("A")
        assert provider.search("A", "where storage", "2026-06-01")["hits"][0]["result"]["value"] == "DuckDB"


def test_restart_reuses_sdk_persistence_and_close_releases_qdrant_lock(store, tmp_path):
    first = SyntheticEmbeddings()
    with make_provider(store, tmp_path, first) as provider:
        provider.index("A")
        assert provider.index("A")["cached"] == 2
        assert len(first.documents) == 2
    second = SyntheticEmbeddings()
    with make_provider(store, tmp_path, second) as restarted:
        assert restarted.index("A")["cached"] == 2
        assert second.documents == []
        assert restarted.search("A", "where storage", "2026-04-10")["hits"]
        assert second.queries == ["where storage"]
    assert store.count() == 6


def test_two_projects_and_unknown_empty_scope_never_fall_back_to_other_sources(store, tmp_path):
    embedder = SyntheticEmbeddings()
    with make_provider(store, tmp_path, embedder) as provider:
        provider.index("A")
        provider.index("B")
        provider.index("missing")
        before = len(embedder.queries)
        assert provider.search("missing", "where storage", "2026-04-10")["hits"] == []
        assert len(embedder.queries) == before
        result = provider.search("B", "where storage", "2026-04-10")["hits"][0]["result"]
        assert result["value"] == "SQLite"
        assert {item["project_id"] for item in result["evidence"]} == {"B"}


def test_mem0_empty_results_are_not_supplemented_from_the_readout_ledger(store, tmp_path, monkeypatch):
    with make_provider(store, tmp_path) as provider:
        provider.index("A")
        monkeypatch.setattr(provider._memory, "search", lambda *args, **kwargs: {"results": []})
        assert provider.search("A", "where storage", "2026-04-10")["hits"] == []


@pytest.mark.parametrize("field", ["project_id", "snapshot_id", "source_ids"])
def test_sdk_scope_or_source_mapping_violations_raise_and_are_counted(store, tmp_path, monkeypatch, field):
    with make_provider(store, tmp_path) as provider:
        provider.index("A")
        actual_search = provider._memory.search

        def corrupted(*args, **kwargs):
            response = actual_search(*args, **kwargs)
            response["results"][0]["metadata"][field] = "another-scope"
            return response

        monkeypatch.setattr(provider._memory, "search", corrupted)
        with pytest.raises(ScopeViolationError, match="scope violation"):
            provider.search("A", "where storage", "2026-04-10")
        assert provider.safe_metadata()["scope_violation_count"] == 1


def test_raw_semantic_threshold_is_strict_and_backend_rank_does_not_override_it(store, tmp_path, monkeypatch):
    with make_provider(store, tmp_path) as provider:
        provider.index("A")
        actual_search = provider._memory.search

        def boundary(*args, **kwargs):
            response = actual_search(*args, **kwargs)
            response["results"][0]["score_details"]["semantic_score"] = 0.55
            response["results"][0]["score"] = 1.0
            return response

        monkeypatch.setattr(provider._memory, "search", boundary)
        assert provider.search("A", "where storage", "2026-04-10", min_cosine=0.55)["hits"] == []


def test_bridge_upstream_failure_is_not_retried_or_exposed_as_a_fake_empty_answer(store, tmp_path):
    embedder = SyntheticEmbeddings()
    with make_provider(store, tmp_path, embedder) as provider:
        provider.index("A")
        embedder.fail_query = True
        with pytest.raises(MemoryBackendError) as raised:
            provider.search("A", "where storage", "2026-04-10")
        assert "synthetic-sensitive-upstream-error" not in str(raised.value)
        assert embedder.queries == ["where storage"]
        assert provider.safe_metadata()["bridge"]["rejected_requests"] == 1


def test_bridge_denies_llm_requests_and_does_not_disclose_its_ephemeral_key(store, tmp_path):
    with make_provider(store, tmp_path) as provider:
        provider.index("A")
        bridge = provider._bridge
        call = Request(bridge.url + "/chat/completions", data=b"{}", method="POST",
                       headers={"Authorization": "Bearer " + bridge.key})
        with pytest.raises(HTTPError) as raised:
            build_opener(ProxyHandler({})).open(call, timeout=5)
        assert raised.value.code == 400
        raised.value.close()
        metadata = provider.safe_metadata()
        assert metadata["bridge"]["llm_attempts"] == 1
        assert bridge.key not in json.dumps(metadata)


def test_failed_partial_index_is_preserved_and_cannot_be_reopened_as_ready(store, tmp_path):
    embedder = SyntheticEmbeddings()
    embedder.fail_predicate = "workers"
    with make_provider(store, tmp_path, embedder) as provider:
        with pytest.raises(MemoryBackendError, match="index failed"):
            provider.index("A")
        with pytest.raises(SearchIndexError):
            provider.search("A", "where storage", "2026-04-10")
    with pytest.raises(MemoryBackendError, match="incomplete"):
        make_provider(store, tmp_path)


def test_state_directory_cannot_be_reused_for_another_run_or_model(store, tmp_path):
    with make_provider(store, tmp_path) as provider:
        provider.index("A")
    with pytest.raises(MemoryBackendError, match="another run/model/schema"):
        Mem0MemoryProvider(store, SyntheticEmbeddings(), tmp_path / "mem0-state", "different-run")
    changed = SyntheticEmbeddings()
    changed.fingerprint = "different-model"
    with pytest.raises(MemoryBackendError, match="another run/model/schema"):
        make_provider(store, tmp_path, changed)


def test_dimension_probe_for_minimal_embedder_is_reused_without_duplicate_model_call(store, tmp_path):
    embedder = SyntheticEmbeddings()
    del embedder.config
    embedder.dimension = None
    with make_provider(store, tmp_path, embedder) as provider:
        provider.index("A")
        assert len(embedder.documents) == 2
        assert provider.safe_metadata()["bridge"]["dimension_probe_reuse"] == 1


def test_only_plan_and_conflict_keys_preserve_shared_resolver_refusals(store, tmp_path):
    store.import_events([
        event("deploy-plan", predicate="deployment", value="VM", kind="plan", effective="2026-04-01T00:00:00Z"),
        event("database-conflict", value="SQLite", observed="2026-04-03T00:00:00Z", effective="2026-04-01T00:00:00Z"),
    ])
    with make_provider(store, tmp_path) as provider:
        provider.index("A")
        only_plan = provider.search("A", "deployment", "2026-05-01")["hits"][0]["result"]
        conflict = provider.search("A", "where storage", "2026-05-01")["hits"][0]["result"]
        assert only_plan["status"] == "unknown" and only_plan["value"] is None
        assert conflict["status"] == "insufficient_evidence" and conflict["value"] is None
