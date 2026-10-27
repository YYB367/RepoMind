"""Synthetic vectors test ranking and safety, not real embedding model quality."""

import json
import math

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import Event
from repomind.intelligence.search import (
    EmbeddingValidationError,
    HybridMemorySearch,
    SearchConfigurationError,
    SearchIndexError,
    build_documents,
    cosine_similarity,
    tokenize,
)


class TinyEmbedder:
    """Explicit vector table for tests only; no model or semantic claim."""

    def __init__(self, properties=None, queries=None, fingerprint="synthetic-test-vector-v1"):
        self.properties = properties or {}
        self.queries = queries or {}
        self.fingerprint = fingerprint
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            if text in self.queries:
                vectors.append(self.queries[text])
            else:
                _, predicate, _ = json.loads(text)
                vectors.append(self.properties[predicate])
        return vectors


def event(event_id="e1", predicate="database", value="MySQL", *,
          project="A", subject="project", observed="2026-01-01T00:00:00Z",
          effective=None, kind="declare", supersedes=None, source="session-1"):
    row = {
        "event_id": event_id, "project_id": project, "subject": subject,
        "predicate": predicate, "value": value, "event_type": kind,
        "observed_at": observed, "effective_at": effective or observed, "source_id": source,
    }
    if supersedes is not None:
        row["supersedes_event_id"] = supersedes
    return row


def import_rows(store, tmp_path, *rows):
    target = tmp_path / "import.jsonl"
    target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return store.import_jsonl(target)


@pytest.fixture
def store(tmp_path):
    with SQLiteMemoryStore(tmp_path / "memory.db") as value:
        yield value


def test_english_lexical_casefold_and_source_evidence(store, tmp_path):
    import_rows(store, tmp_path, event(), event("e2", "framework", "FastAPI"))
    response = HybridMemorySearch(store).search("A", "DATABASE?", "2026-02-01", mode="lexical")
    assert [hit["predicate"] for hit in response["hits"]] == ["database"]
    assert response["hits"][0]["result"]["value"] == "MySQL"
    assert response["hits"][0]["result"]["evidence"][0]["source_id"] == "session-1"
    assert response["hits"][0]["semantic_score"] is None
    json.dumps(response, allow_nan=False)


def test_unicode_and_chinese_bigram_lexical_retrieval(store, tmp_path):
    import_rows(store, tmp_path, event(predicate="数据库", value="PostgreSQL"),
                event("e2", "框架", "Django"))
    response = HybridMemorySearch(store).search("A", "现在数据库是什么", "2026-02-01", mode="lexical")
    assert [hit["predicate"] for hit in response["hits"]] == ["数据库"]
    assert tokenize("ÉCOLE 数据库") == {"école": 1, "数据": 1, "据库": 1}


@pytest.mark.parametrize("query", ["unrecorded-topic", "???", "完全不存在"])
def test_lexical_without_token_overlap_returns_no_hit(store, tmp_path, query):
    import_rows(store, tmp_path, event())
    provider = TinyEmbedder()
    response = HybridMemorySearch(store, provider).search("A", query, "2026-02-01", mode="lexical")
    assert response["hits"] == []
    assert provider.calls == []


def test_semantic_modes_require_provider_and_explicit_index(store, tmp_path):
    import_rows(store, tmp_path, event())
    search = HybridMemorySearch(store)
    with pytest.raises(SearchConfigurationError, match="provider"):
        search.index("A")
    for mode in ("semantic", "hybrid"):
        with pytest.raises(SearchConfigurationError, match="provider"):
            search.search("A", "storage", "2026-02-01", mode=mode)
    provider = TinyEmbedder({"database": [1, 0]}, {"storage": [1, 0]})
    with pytest.raises(SearchIndexError, match="reindex"):
        HybridMemorySearch(store, provider).search("A", "storage", "2026-02-01")
    assert provider.calls == []


def test_index_batches_only_missing_documents_and_query_embeds_once(store, tmp_path):
    import_rows(store, tmp_path, event(), event("e2", "framework", "FastAPI"))
    provider = TinyEmbedder({"database": [1, 0], "framework": [0, 1]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    first = search.index("A")
    assert (first["count"], first["requested"], first["cached"]) == (2, 2, 0)
    assert len(provider.calls) == 1 and len(provider.calls[0]) == 2
    second = search.index("A")
    assert (second["requested"], second["cached"]) == (0, 2)
    assert len(provider.calls) == 1
    response = search.search("A", "storage", "2026-02-01", mode="semantic")
    assert [hit["predicate"] for hit in response["hits"]] == ["database"]
    assert provider.calls[-1] == ["storage"]
    assert len(provider.calls) == 2


def test_cached_vectors_survive_store_and_process_client_restart(tmp_path):
    database = tmp_path / "memory.db"
    first = TinyEmbedder({"database": [1, 0]})
    with SQLiteMemoryStore(database) as store:
        import_rows(store, tmp_path, event())
        HybridMemorySearch(store, first).index("A")
    second = TinyEmbedder(queries={"storage": [1, 0]})
    with SQLiteMemoryStore(database) as reopened:
        search = HybridMemorySearch(reopened, second)
        assert search.index("A")["cached"] == 1
        result = search.search("A", "storage", "2026-02-01", mode="semantic")
    assert result["hits"][0]["result"]["value"] == "MySQL"
    assert second.calls == [["storage"]]


def test_changed_history_requires_reindex_and_resolves_complete_history(store, tmp_path):
    import_rows(store, tmp_path, event(), event("framework", "framework", "Django"))
    provider = TinyEmbedder({"database": [1, 0], "framework": [0, 1]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    import_rows(store, tmp_path, event("e2", value="PostgreSQL", kind="complete",
                                     observed="2026-03-02T00:00:00Z", effective="2026-03-01T00:00:00Z"))
    with pytest.raises(SearchIndexError, match="stale"):
        search.search("A", "storage", "2026-03-10", mode="semantic")
    assert len(provider.calls) == 1
    reindex = search.index("A")
    assert (reindex["requested"], reindex["cached"]) == (1, 1)
    before = search.search("A", "storage", "2026-02-28", mode="semantic")["hits"][0]
    after = search.search("A", "storage", "2026-03-01", mode="semantic")["hits"][0]
    assert before["result"]["value"] == "MySQL"
    assert after["result"]["value"] == "PostgreSQL"
    assert after["result"]["considered_event_ids"] == ["e1", "e2"]


def test_new_property_also_invalidates_complete_index(store, tmp_path):
    import_rows(store, tmp_path, event())
    provider = TinyEmbedder({"database": [1, 0], "framework": [0, 1]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    import_rows(store, tmp_path, event("e2", "framework", "FastAPI"))
    with pytest.raises(SearchIndexError, match="reindex"):
        search.search("A", "storage", "2026-02-01", mode="hybrid")
    assert search.index("A")["requested"] == 1


def test_distinct_fingerprints_keep_multiple_dimensions_and_cache_versions(store, tmp_path):
    import_rows(store, tmp_path, event())
    first = TinyEmbedder({"database": [1, 0]}, {"storage": [1, 0]}, fingerprint="model-at-endpoint-one")
    second = TinyEmbedder({"database": [1, 0, 0]}, {"storage": [1, 0, 0]}, fingerprint="model-at-endpoint-two")
    one, two = HybridMemorySearch(store, first), HybridMemorySearch(store, second)
    assert one.index("A")["requested"] == 1
    with pytest.raises(SearchIndexError):
        two.search("A", "storage", "2026-02-01", mode="semantic")
    assert two.index("A")["requested"] == 1
    assert one.index("A")["cached"] == 1
    assert one.search("A", "storage", "2026-02-01", mode="semantic")["hits"]
    assert two.search("A", "storage", "2026-02-01", mode="semantic")["hits"]


def test_observation_slices_never_embed_future_content_and_cache_separately(store, tmp_path):
    import_rows(store, tmp_path, event(), event("e2", value="SECRET-FUTURE", kind="complete",
                                     observed="2026-03-02T00:00:00Z", effective="2026-03-01T00:00:00Z"),
                event("e3", "future-only", "SECRET-PROPERTY", observed="2026-04-01T00:00:00Z"))
    provider = TinyEmbedder({"database": [1, 0], "future-only": [0, 1]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    historical = search.index("A", known_at="2026-02-01")
    assert historical["count"] == 1
    assert "SECRET" not in " ".join(provider.calls[0])
    assert search.index("A")["requested"] == 2
    assert search.index("A", known_at="2026-02-01")["cached"] == 1
    response = search.search("A", "storage", "2026-03-10", known_at="2026-02-01", mode="semantic")
    assert response["hits"][0]["result"]["value"] == "MySQL"
    assert response["hits"][0]["result"]["considered_event_ids"] == ["e1"]


def test_full_history_cache_cannot_stand_in_for_a_historical_document(store, tmp_path):
    import_rows(store, tmp_path, event(), event("e2", value="PostgreSQL", kind="complete",
                                     observed="2026-03-02T00:00:00Z", effective="2026-03-01T00:00:00Z"))
    provider = TinyEmbedder({"database": [1, 0]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    with pytest.raises(SearchIndexError, match="reindex"):
        search.search("A", "storage", "2026-03-10", known_at="2026-02-01", mode="semantic")
    assert len(provider.calls) == 1


def test_project_and_subject_boundaries_apply_before_embedding_and_resolution(store, tmp_path):
    import_rows(store, tmp_path, event(), event("other-project", value="SECRET-OTHER-PROJECT", project="B"),
                event("sandbox", value="SQLite", subject="sandbox"))
    provider = TinyEmbedder({"database": [1, 0]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    assert search.index("A")["count"] == 2
    assert "SECRET" not in " ".join(provider.calls[0])
    hits = search.search("A", "storage", "2026-02-01", mode="semantic")["hits"]
    assert {hit["subject"]: hit["result"]["value"] for hit in hits} == {"project": "MySQL", "sandbox": "SQLite"}
    assert all(evidence["project_id"] == "A" for hit in hits for evidence in hit["result"]["evidence"])
    before = len(provider.calls)
    assert search.search("missing", "storage", "2026-02-01", mode="semantic")["hits"] == []
    assert search.search("missing", "database", "2026-02-01", mode="lexical")["hits"] == []
    assert len(provider.calls) == before


def test_plan_match_does_not_promote_plan_to_actual_state(store, tmp_path):
    import_rows(store, tmp_path, event(), event("plan", value="PostgreSQL", kind="plan",
                                     observed="2026-02-01T00:00:00Z", effective="2026-03-01T00:00:00Z"))
    hit = HybridMemorySearch(store).search("A", "PostgreSQL", "2026-04-01", mode="lexical")["hits"][0]
    assert hit["result"]["value"] == "MySQL"
    assert hit["result"]["plan_event_ids"] == ["plan"]
    assert [row["event_id"] for row in hit["result"]["evidence"]] == ["e1"]


def test_only_plan_property_can_be_retrieved_but_answer_remains_unknown(store, tmp_path):
    import_rows(store, tmp_path, event(kind="plan", value="Redis", predicate="cache",
                                     effective="2026-03-01T00:00:00Z"))
    hit = HybridMemorySearch(store).search("A", "Redis", "2026-04-01", mode="lexical")["hits"][0]
    assert hit["result"]["status"] == "unknown"
    assert hit["result"]["value"] is None
    assert hit["result"]["evidence"] == []


def test_semantic_hit_resolves_corrections_with_optional_knowledge_cutoff(store, tmp_path):
    import_rows(store, tmp_path, event(), event("correction", value="PostgreSQL", kind="correct",
                        observed="2026-02-01T00:00:00Z", effective="2026-01-01T00:00:00Z", supersedes="e1"))
    provider = TinyEmbedder({"database": [1, 0]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    latest = search.search("A", "storage", "2026-01-15", mode="semantic")["hits"][0]["result"]
    assert latest["value"] == "PostgreSQL"
    assert [row["event_id"] for row in latest["evidence"]] == ["correction"]
    search.index("A", known_at="2026-01-31")
    old = search.search("A", "storage", "2026-01-15", known_at="2026-01-31", mode="semantic")["hits"][0]["result"]
    assert old["value"] == "MySQL"


def test_conflicting_facts_remain_insufficient_even_with_high_similarity(store, tmp_path):
    import_rows(store, tmp_path, event(), event("conflict", value="PostgreSQL"))
    provider = TinyEmbedder({"database": [1, 0]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    hit = search.search("A", "storage", "2026-02-01", mode="semantic")["hits"][0]
    assert hit["semantic_score"] == pytest.approx(1)
    assert hit["result"]["status"] == "insufficient_evidence"
    assert hit["result"]["value"] is None
    assert {row["event_id"] for row in hit["result"]["evidence"]} == {"e1", "conflict"}


def test_rrf_uses_positive_route_ranks_and_stable_ties(store, tmp_path):
    import_rows(store, tmp_path, event(source="s"),
                event("deploy", "deployment", "database helper", source="s"),
                event("region", "region", "Europe", source="s"))
    provider = TinyEmbedder(
        {"database": [0.8, 0.6], "deployment": [1, 0], "region": [0.5, math.sqrt(0.75)]},
        {"database": [1, 0]},
    )
    search = HybridMemorySearch(store, provider)
    search.index("A")
    hits = search.search("A", "database", "2026-02-01", mode="hybrid")["hits"]
    assert [hit["predicate"] for hit in hits] == ["database", "deployment", "region"]
    assert hits[0]["score"] == pytest.approx(1 / 61 + 1 / 62)
    assert hits[1]["score"] == pytest.approx(1 / 61 + 1 / 62)
    assert hits[2]["score"] == pytest.approx(1 / 63)
    assert hits[2]["lexical_score"] == 0


def test_similarity_cutoff_excludes_orthogonal_or_negative_matches(store, tmp_path):
    import_rows(store, tmp_path, event(), event("e2", "framework", "Django"))
    provider = TinyEmbedder({"database": [0, 1], "framework": [-1, 0]}, {"no-match": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    assert search.search("A", "no-match", "2026-02-01", mode="semantic", min_cosine=0)["hits"] == []
    assert search.search("A", "no-match", "2026-02-01", mode="hybrid", min_cosine=0)["hits"] == []
    # A lexical route can still retrieve a property with an orthogonal embedding.
    assert [hit["predicate"] for hit in search.search("A", "database", "2026-02-01", mode="lexical")["hits"]] == ["database"]


@pytest.mark.parametrize("invalid", [[], [0, 0], [float("nan"), 1], [float("inf"), 1],
                                       [1, float("-inf")], [True, 1], ["1", 0], [10 ** 500, 1]])
def test_invalid_document_vectors_are_rejected_before_cache_write(store, tmp_path, invalid):
    import_rows(store, tmp_path, event())
    provider = TinyEmbedder({"database": invalid})
    with pytest.raises(EmbeddingValidationError):
        HybridMemorySearch(store, provider).index("A")
    assert store.connection.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0] == 0


def test_mixed_document_dimensions_are_rejected_atomically(store, tmp_path):
    import_rows(store, tmp_path, event(), event("e2", "framework", "FastAPI"))
    provider = TinyEmbedder({"database": [1, 0], "framework": [1, 0, 0]})
    with pytest.raises(EmbeddingValidationError, match="dimensions"):
        HybridMemorySearch(store, provider).index("A")
    assert store.connection.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0] == 0


@pytest.mark.parametrize("invalid", [[0, 0], [1, float("nan")], [1, 0, 0]])
def test_invalid_query_vector_or_mismatched_dimensions_rejected(store, tmp_path, invalid):
    import_rows(store, tmp_path, event())
    provider = TinyEmbedder({"database": [1, 0]}, {"storage": invalid})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    with pytest.raises(EmbeddingValidationError):
        search.search("A", "storage", "2026-02-01", mode="semantic")


def test_corrupt_cached_vectors_fail_before_query_embedding(store, tmp_path, monkeypatch):
    import_rows(store, tmp_path, event(), event("e2", "framework", "FastAPI"))
    provider = TinyEmbedder({"database": [1, 0], "framework": [0, 1]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    original = store.get_vector

    def mismatched(project_id, subject, predicate, fingerprint, text_hash):
        return [1, 0, 0] if predicate == "framework" else original(project_id, subject, predicate, fingerprint, text_hash)

    monkeypatch.setattr(store, "get_vector", mismatched)
    with pytest.raises(SearchIndexError, match="dimensions"):
        search.search("A", "storage", "2026-02-01", mode="semantic")
    assert len(provider.calls) == 1
    monkeypatch.setattr(store, "get_vector", lambda *args: [float("nan"), 1])
    with pytest.raises(SearchIndexError, match="reindex"):
        search.search("A", "storage", "2026-02-01", mode="semantic")


def test_provider_cardinality_failure_never_writes_partial_index(store, tmp_path):
    import_rows(store, tmp_path, event(), event("e2", "framework", "FastAPI"))
    provider = TinyEmbedder()
    provider.embed = lambda texts: [[1, 0]]
    with pytest.raises(EmbeddingValidationError, match="number"):
        HybridMemorySearch(store, provider).index("A")
    assert store.connection.execute("SELECT COUNT(*) FROM memory_vectors").fetchone()[0] == 0


def test_query_provider_cardinality_must_be_exactly_one(store, tmp_path):
    import_rows(store, tmp_path, event())
    provider = TinyEmbedder({"database": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    provider.embed = lambda texts: [[1, 0], [1, 0]]
    with pytest.raises(EmbeddingValidationError, match="exactly one"):
        search.search("A", "storage", "2026-02-01", mode="semantic")


@pytest.mark.parametrize("kwargs", [{"top_k": 0}, {"top_k": 101}, {"top_k": True},
                                      {"top_k": 1.5}, {"mode": "unknown"},
                                      {"min_cosine": -0.1}, {"min_cosine": 1},
                                      {"min_cosine": float("nan")}, {"min_cosine": True}])
def test_invalid_search_settings_are_diagnostic(store, kwargs):
    kwargs = dict(kwargs)
    with pytest.raises(ValueError):
        HybridMemorySearch(store).search("A", "database", "2026-02-01", mode=kwargs.pop("mode", "lexical"), **kwargs)


@pytest.mark.parametrize("arguments", [("", "database", "2026-02-01"),
                                        ("A", " ", "2026-02-01"),
                                        ("A", "database", "2026-02-01T10:00:00")])
def test_invalid_scope_query_or_implicit_local_time_is_rejected(store, arguments):
    with pytest.raises(ValueError):
        HybridMemorySearch(store).search(*arguments, mode="lexical")


def test_top_k_and_semantic_cutoff_are_applied_after_ranking(store, tmp_path):
    import_rows(store, tmp_path, event(), event("e2", "framework", "Django"))
    provider = TinyEmbedder({"database": [1, 0], "framework": [0.8, 0.6]}, {"stack": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")
    assert len(search.search("A", "stack", "2026-02-01", mode="semantic", top_k=1)["hits"]) == 1
    assert len(search.search("A", "stack", "2026-02-01", mode="semantic", min_cosine=0.9)["hits"]) == 1


def test_cosine_is_stable_for_finite_extreme_values():
    assert cosine_similarity([1e308, 1e308], [1e308, 1e308]) == pytest.approx(1)
    assert cosine_similarity([1e-308, 1e-308], [1e-308, -1e-308]) == pytest.approx(0)
    with pytest.raises(EmbeddingValidationError):
        cosine_similarity([1, 0], [1, 0, 0])


def test_document_builder_is_scope_safe_deterministic_and_delimiter_safe():
    rows = [Event.model_validate(event("e2", value="second")),
            Event.model_validate(event()), Event.model_validate(event("other", project="B"))]
    forward, reverse = build_documents(rows), build_documents(reversed(rows))
    assert forward == reverse
    assert len(forward) == 2
    assert {document["project_id"] for document in forward} == {"A", "B"}
    assert all("second" not in document["text"] for document in forward if document["project_id"] == "B")
    # Tabs in values and source names must not create identical cache inputs.
    first = build_documents([Event.model_validate(event(value="a\tb", source="c"))])[0]
    second = build_documents([Event.model_validate(event(value="a", source="b\tc"))])[0]
    assert first["text_hash"] != second["text_hash"]


def test_store_cache_validation_error_is_reported_as_reindex(store, tmp_path, monkeypatch):
    import_rows(store, tmp_path, event())
    provider = TinyEmbedder({"database": [1, 0]}, {"storage": [1, 0]})
    search = HybridMemorySearch(store, provider)
    search.index("A")

    def corrupt(*args):
        raise ValueError("stored embedding dimension metadata is corrupt")

    monkeypatch.setattr(store, "get_vector", corrupt)
    with pytest.raises(SearchIndexError, match="reindex"):
        search.search("A", "storage", "2026-02-01", mode="semantic")
    assert len(provider.calls) == 1


def test_model_fingerprint_is_required_before_model_calls(store):
    provider = TinyEmbedder(fingerprint=" ")
    with pytest.raises(SearchConfigurationError, match="fingerprint"):
        HybridMemorySearch(store, provider).index("A")
    assert provider.calls == []


def test_optional_query_embedding_route_does_not_mix_document_and_query_calls(store, tmp_path):
    import_rows(store, tmp_path, event())

    class RoutedEmbedder(TinyEmbedder):
        def __init__(self):
            super().__init__({"database": [1, 0]})
            self.query_calls = []

        def embed_query(self, text):
            self.query_calls.append(text)
            return [1, 0]

    provider = RoutedEmbedder()
    search = HybridMemorySearch(store, provider)
    search.index("A")
    result = search.search("A", "storage", "2026-02-01", mode="semantic")
    assert result["hits"][0]["result"]["value"] == "MySQL"
    assert provider.query_calls == ["storage"]
    assert len(provider.calls) == 1
    assert json.loads(provider.calls[0][0])[1] == "database"


@pytest.mark.parametrize("invalid", [[0, 0], [float("nan"), 1], [1, 0, 0]])
def test_optional_query_route_still_rejects_bad_or_mismatched_vectors(store, tmp_path, invalid):
    import_rows(store, tmp_path, event())
    provider = TinyEmbedder({"database": [1, 0]})
    provider.embed_query = lambda text: invalid
    search = HybridMemorySearch(store, provider)
    search.index("A")
    with pytest.raises(EmbeddingValidationError):
        search.search("A", "storage", "2026-02-01", mode="semantic")
    assert len(provider.calls) == 1


def test_noncallable_optional_query_attribute_uses_existing_embedding_fallback(store, tmp_path):
    import_rows(store, tmp_path, event())
    provider = TinyEmbedder({"database": [1, 0]}, {"storage": [1, 0]})
    provider.embed_query = None
    search = HybridMemorySearch(store, provider)
    search.index("A")
    assert search.search("A", "storage", "2026-02-01", mode="semantic")["hits"]
    assert provider.calls[-1] == ["storage"]
