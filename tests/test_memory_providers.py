"""Native controlled arms and the evidence-free baseline; no real services."""

import json
from types import SimpleNamespace

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.comparison.providers import NativeMemoryProvider, NoMemoryProvider
from repomind.comparison.base import ScopeViolationError
from repomind.domain.models import Event


class SyntheticEmbeddings:
    """Hand-authored routing vectors, not a language model quality test."""
    fingerprint = "comparison-synthetic-v1"
    dimension = 2

    def __init__(self):
        self.documents, self.queries = [], []
        self.config = SimpleNamespace(embedding_model="synthetic-vector-model", embedding_dimensions=2)

    def embed(self, texts):
        self.documents.extend(texts)
        return [[1.0, 0.0] if json.loads(text)[1] == "database" else [0.0, 1.0] for text in texts]

    def embed_query(self, text):
        self.queries.append(text)
        return [1.0, 0.0] if text == "where storage" else [-1.0, -1.0]


def events():
    return [Event(event_id="declared", project_id="A", source_id="session-1", subject="project",
                  predicate="database", value="MySQL", event_type="declare", observed_at="2026-01-01T00:00:00Z"),
            Event(event_id="plan", project_id="A", source_id="session-2", subject="project",
                  predicate="database", value="PostgreSQL", event_type="plan", observed_at="2026-02-01T00:00:00Z",
                  effective_at="2026-04-01T00:00:00Z"),
            Event(event_id="complete", project_id="A", source_id="session-3", subject="project",
                  predicate="database", value="PostgreSQL", event_type="complete", observed_at="2026-04-02T00:00:00Z",
                  effective_at="2026-04-01T00:00:00Z")]


def test_no_memory_arm_never_reads_the_supplied_ledger_or_creates_an_embedder():
    class UnreadableStore:
        def __getattr__(self, name):
            raise AssertionError("no_memory must not read project history")

    with NoMemoryProvider(UnreadableStore()) as provider:
        assert provider.index("A")["count"] == 0
        result = provider.search("A", "where\nstorage", "2026-05-01")
        assert result["hits"] == []
        assert result["query"] == "where storage"
        assert result["reason"] == "no_memory_baseline"
        assert provider.safe_metadata()["embedding"] is None


@pytest.mark.parametrize("mode", ["semantic", "hybrid"])
def test_native_arms_share_original_temporal_resolution_and_normalized_query(tmp_path, mode):
    embedder = SyntheticEmbeddings()
    with SQLiteMemoryStore(tmp_path / "memory.db") as store:
        store.import_events(events())
        with NativeMemoryProvider(store, embedder, mode=mode) as provider:
            assert provider.name == "repomind_" + mode
            provider.index("A")
            before = provider.search("A", "where\nstorage", "2026-03-01")["hits"][0]["result"]
            after = provider.search("A", "where storage", "2026-04-10")["hits"][0]["result"]
            assert before["value"] == "MySQL"
            assert before["plan_event_ids"] == ["plan"]
            assert after["value"] == "PostgreSQL"
            assert [item["source_id"] for item in after["evidence"]] == ["session-3"]
            assert embedder.queries == ["where storage", "where storage"]
        assert store.count() == 3  # runner, not provider, owns this ledger


def test_independent_native_arms_do_not_share_embedding_cache_or_client_calls(tmp_path):
    clients = [SyntheticEmbeddings(), SyntheticEmbeddings()]
    for index, mode in enumerate(("semantic", "hybrid")):
        with SQLiteMemoryStore(tmp_path / f"variant-{index}.db") as store:
            store.import_events(events())
            provider = NativeMemoryProvider(store, clients[index], mode)
            assert provider.index("A")["requested"] == 1
            assert provider.index("A")["cached"] == 1
    assert clients[0].documents == clients[1].documents
    assert len(clients[0].documents) == len(clients[1].documents) == 1


def test_native_arm_rejects_lexical_only_or_unknown_variant():
    with pytest.raises(ValueError, match="semantic or hybrid"):
        NativeMemoryProvider(None, None, mode="lexical")


@pytest.mark.parametrize("settings", [{"top_k": 0}, {"min_cosine": float("nan")}, {"known_at": "local time"}])
def test_baseline_validates_same_scope_and_query_contract(settings):
    with pytest.raises(ValueError):
        NoMemoryProvider().search("A", "where storage", "2026-05-01", **settings)


def test_native_scope_violation_is_reported_before_silent_filtering_or_embedding():
    class WrongScopeStore:
        def project_events(self, project_id, known_at=None):
            return [events()[0].model_copy(update={"project_id": "another-project"})]

    embedder = SyntheticEmbeddings()
    provider = NativeMemoryProvider(WrongScopeStore(), embedder)
    with pytest.raises(ScopeViolationError, match="scope violation"):
        provider.index("A")
    assert provider.safe_metadata()["scope_violation_count"] == 1
    assert embedder.documents == []
