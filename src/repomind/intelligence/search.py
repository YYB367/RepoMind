"""Project-scoped property retrieval; answers always use the V1 fact resolver.

Embeddings rank a document for each (subject, predicate), never individual facts.
The complete matching ledger is then resolved at the requested effective time.
This module has no default embedding model and makes no model quality claim.
"""

from collections import Counter
from collections.abc import Iterable
from datetime import datetime
import hashlib
import json
import math
from numbers import Real
import re
from typing import Any, Protocol

from repomind.domain.models import Event, MemoryQuery, parse_timestamp
from repomind.memory.retriever import MemoryRetriever


class SearchConfigurationError(ValueError):
    """A semantic search was requested without a usable embedding provider."""


class SearchIndexError(ValueError):
    """The selected project/model/observation slice needs reindexing."""


class EmbeddingValidationError(ValueError):
    """An embedding is invalid or has incompatible dimensions."""


class EmbeddingProvider(Protocol):
    @property
    def fingerprint(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SearchStore(Protocol):
    def project_events(self, project_id: str, known_at: datetime | None = None) -> list[Event]: ...

    def get_vector(self, project_id: str, subject: str, predicate: str,
                   fingerprint: str, text_hash: str) -> list[float] | None: ...

    def put_vectors(self, records: list[dict[str, Any]]) -> None: ...

    def list_events(self, query: MemoryQuery) -> list[Event]: ...


_CJK = r"\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_TOKENS = re.compile(rf"[{_CJK}]+|[^\W_{_CJK}]+", re.UNICODE)
_CJK_RUN = re.compile(rf"^[{_CJK}]+$")


def tokenize(text: str) -> Counter[str]:
    """Unicode word counts plus CJK bigrams, without a language dictionary."""
    tokens: list[str] = []
    for word in _TOKENS.findall(text.casefold()):
        if _CJK_RUN.fullmatch(word) and len(word) > 1:
            tokens.extend(word[index:index + 2] for index in range(len(word) - 1))
        else:
            tokens.append(word)
    return Counter(tokens)


def _lexical_score(query: Counter[str], document: Counter[str]) -> float:
    numerator = sum(count * document.get(token, 0) for token, count in query.items())
    if not numerator:
        return 0.0
    query_norm = math.sqrt(sum(count * count for count in query.values()))
    document_norm = math.sqrt(sum(count * count for count in document.values()))
    return numerator / (query_norm * document_norm)


def validate_vector(vector: object, *, context: str = "embedding") -> list[float]:
    """Reject empty, zero, nonfinite and nonnumeric provider/cache vectors."""
    if not isinstance(vector, list) or not vector:
        raise EmbeddingValidationError(f"{context}: expected a nonempty numeric vector")
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in vector):
        raise EmbeddingValidationError(f"{context}: vector elements must be finite numbers")
    try:
        normalized = [float(value) for value in vector]
    except (OverflowError, ValueError) as exc:
        raise EmbeddingValidationError(f"{context}: vector elements must be finite numbers") from exc
    if not all(math.isfinite(value) for value in normalized):
        raise EmbeddingValidationError(f"{context}: vector elements must be finite numbers")
    if not any(value != 0.0 for value in normalized):
        raise EmbeddingValidationError(f"{context}: zero vectors are not searchable")
    return normalized


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Stable cosine, including very large or very small finite components."""
    left = validate_vector(left)
    right = validate_vector(right)
    if len(left) != len(right):
        raise EmbeddingValidationError("query and index vector dimensions differ; reindex with one model")
    left_scale, right_scale = max(map(abs, left)), max(map(abs, right))
    left_unit = [value / left_scale for value in left]
    right_unit = [value / right_scale for value in right]
    left_norm, right_norm = math.hypot(*left_unit), math.hypot(*right_unit)
    score = math.fsum((x / left_norm) * (y / right_norm)
                      for x, y in zip(left_unit, right_unit))
    return max(-1.0, min(1.0, score))


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value.strip()


def _timestamp(value: object | None) -> datetime | None:
    return None if value is None else parse_timestamp(value, allow_date=True)


def document_text(subject: str, predicate: str, events: Iterable[Event]) -> str:
    """Canonical model input, reusable when recording explicit test responses."""
    return json.dumps(
        [subject, predicate,
         [[event.event_type, event.value, event.source_id]
          for event in sorted(events, key=lambda item: item.event_id)]],
        ensure_ascii=False, separators=(",", ":"),
    )


def build_documents(events: Iterable[Event]) -> list[dict[str, Any]]:
    """Build deterministic property documents without combining project scopes.

    Callers must apply their observation cutoff before building documents.
    This function does not consult queries, expected answers, or an embedder.
    """
    groups: dict[tuple[str, str, str], list[Event]] = {}
    for event in events:
        groups.setdefault(event.key, []).append(event)
    documents = []
    for (project_id, subject, predicate), history in sorted(groups.items()):
        content = document_text(subject, predicate, history)
        documents.append({
            "project_id": project_id, "subject": subject, "predicate": predicate,
            "text": content, "text_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })
    return documents


class HybridMemorySearch:
    """Lexical or model-backed retrieval within an explicit project boundary.

    ``index`` explicitly embeds missing property documents. ``search`` never
    silently rebuilds an index: a missing or stale document raises an error.
    Observation slices have separate text hashes and may coexist in the cache.
    """

    def __init__(self, store: SearchStore, embedder: EmbeddingProvider | None = None):
        self.store = store
        self.embedder = embedder
        self.retriever = MemoryRetriever(store)

    def _fingerprint(self) -> str:
        if self.embedder is None:
            raise SearchConfigurationError("semantic/hybrid search requires an embedding provider")
        value = self.embedder.fingerprint
        if not isinstance(value, str) or not value.strip():
            raise SearchConfigurationError("embedding provider fingerprint must be a nonempty string")
        return value

    def _documents(self, project_id: str, known_at: datetime | None) -> list[dict[str, Any]]:
        # Defense in depth if an adapter returns another scope or future observations.
        visible = (event for event in self.store.project_events(project_id, known_at=known_at)
                   if event.project_id == project_id
                   and (known_at is None or event.observed_at <= known_at))
        return build_documents(visible)

    def _cached(self, project_id: str, documents: list[dict[str, Any]],
                fingerprint: str) -> tuple[dict[tuple[str, str], list[float]], list[dict[str, Any]]]:
        vectors: dict[tuple[str, str], list[float]] = {}
        missing = []
        dimensions: set[int] = set()
        for document in documents:
            try:
                vector = self.store.get_vector(
                    project_id, document["subject"], document["predicate"],
                    fingerprint, document["text_hash"],
                )
            except (ValueError, TypeError) as exc:
                raise SearchIndexError("invalid cached embedding; reindex this project/model snapshot") from exc
            if vector is None:
                missing.append(document)
                continue
            try:
                vector = validate_vector(vector, context="cached embedding; reindex if invalid")
            except EmbeddingValidationError as exc:
                raise SearchIndexError(str(exc)) from exc
            dimensions.add(len(vector))
            vectors[(document["subject"], document["predicate"])] = vector
        if len(dimensions) > 1:
            raise SearchIndexError("cached vector dimensions differ; reindex with a single model fingerprint")
        return vectors, missing

    def index(self, project_id: str, known_at: object | None = None) -> dict[str, Any]:
        project_id = _text(project_id, "project_id")
        known_at = _timestamp(known_at)
        fingerprint = self._fingerprint()
        documents = self._documents(project_id, known_at)
        vectors, missing = self._cached(project_id, documents, fingerprint)
        if missing:
            returned = self.embedder.embed([document["text"] for document in missing])
            if not isinstance(returned, list) or len(returned) != len(missing):
                raise EmbeddingValidationError("embedding provider returned the wrong number of document vectors")
            validated = [validate_vector(vector, context="document embedding") for vector in returned]
            dimensions = {len(vector) for vector in vectors.values()} | {len(vector) for vector in validated}
            if len(dimensions) > 1:
                raise EmbeddingValidationError("document vector dimensions differ; use a distinct fingerprint for each model")
            records = [
                {"project_id": project_id, "subject": document["subject"],
                 "predicate": document["predicate"], "fingerprint": fingerprint,
                 "text_hash": document["text_hash"], "vector": vector}
                for document, vector in zip(missing, validated)
            ]
            # The store commits this batch atomically after validating every record.
            self.store.put_vectors(records)
        return {"project_id": project_id, "count": len(documents),
                "requested": len(missing), "cached": len(vectors), "fingerprint": fingerprint,
                "known_at": None if known_at is None else known_at.isoformat()}

    def search(self, project_id: str, text: str, as_of: object,
               known_at: object | None = None, top_k: int = 5, mode: str = "hybrid",
               min_cosine: float = 0.2) -> dict[str, Any]:
        project_id, text = _text(project_id, "project_id"), _text(text, "query")
        as_of, known_at = parse_timestamp(as_of, allow_date=True), _timestamp(known_at)
        if mode not in {"lexical", "semantic", "hybrid"}:
            raise ValueError("mode must be lexical, semantic, or hybrid")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise ValueError("top_k must be an integer between 1 and 100")
        if (isinstance(min_cosine, bool) or not isinstance(min_cosine, Real)
                or not math.isfinite(min_cosine) or not 0 <= min_cosine < 1):
            raise ValueError("min_cosine must be finite and between 0 (inclusive) and 1 (exclusive)")
        fingerprint = None if mode == "lexical" else self._fingerprint()
        documents = self._documents(project_id, known_at)
        response = {
            "project_id": project_id, "query": text, "mode": mode,
            "as_of": as_of.isoformat(), "known_at": None if known_at is None else known_at.isoformat(),
            "top_k": top_k, "min_cosine": float(min_cosine), "fingerprint": fingerprint,
            "indexed_documents": len(documents), "hits": [],
        }
        if not documents:
            return response
        lexical: dict[tuple[str, str], float] = {}
        semantic: dict[tuple[str, str], float] = {}
        if mode != "semantic":
            query_tokens = tokenize(text)
            lexical = {
                (document["subject"], document["predicate"]):
                    _lexical_score(query_tokens, tokenize(document["text"]))
                for document in documents
            }
        if mode != "lexical":
            vectors, missing = self._cached(project_id, documents, fingerprint)
            if missing:
                raise SearchIndexError(
                    f"missing/stale index for {len(missing)} property document(s); "
                    "reindex this project with the same provider and known_at before searching"
                )
            embed_query = getattr(self.embedder, "embed_query", None)
            if callable(embed_query):
                query_vector = validate_vector(embed_query(text), context="query embedding")
            else:
                returned = self.embedder.embed([text])
                if not isinstance(returned, list) or len(returned) != 1:
                    raise EmbeddingValidationError("embedding provider must return exactly one query vector")
                query_vector = validate_vector(returned[0], context="query embedding")
            semantic = {key: cosine_similarity(query_vector, vector) for key, vector in vectors.items()}
        lexical_keys = sorted((key for key, score in lexical.items() if score > 0),
                              key=lambda key: (-lexical[key], key))
        semantic_keys = sorted((key for key, score in semantic.items() if score > min_cosine),
                               key=lambda key: (-semantic[key], key))
        if mode == "lexical":
            scores = {key: lexical[key] for key in lexical_keys}
        elif mode == "semantic":
            scores = {key: semantic[key] for key in semantic_keys}
        else:
            scores: dict[tuple[str, str], float] = {}
            for ranked in (lexical_keys, semantic_keys):
                for rank, key in enumerate(ranked, 1):
                    scores[key] = scores.get(key, 0.0) + 1.0 / (60 + rank)
        for subject, predicate in sorted(scores, key=lambda key: (-scores[key], key))[:top_k]:
            key = subject, predicate
            result = self.retriever.query(MemoryQuery(
                project_id=project_id, subject=subject, predicate=predicate,
                as_of=as_of, known_at=known_at,
            ))
            response["hits"].append({
                "subject": subject, "predicate": predicate, "score": scores[key],
                "lexical_score": lexical.get(key, 0.0), "semantic_score": semantic.get(key),
                "result": result.model_dump(mode="json"),
            })
        return response
