"""Small provider contract; no benchmark answers cross this boundary."""

from datetime import datetime
import math
from numbers import Real
from typing import Any, Protocol

from repomind.domain.models import MemoryQuery, parse_timestamp


class ScopeViolationError(ValueError):
    """A backend returned data outside its explicit project/snapshot boundary."""


class ScopedReadout:
    """Validate adapter output before a resolver can discard invalid scope."""

    def __init__(self, store, violation):
        self.store, self.violation = store, violation

    def __getattr__(self, name):
        return getattr(self.store, name)

    def project_events(self, project_id, known_at=None):
        events = self.store.project_events(project_id, known_at=known_at)
        if any(event.project_id != project_id or (known_at is not None and event.observed_at > known_at)
               for event in events):
            self.violation("project/known_at readout differs from requested scope")
        return events

    def list_events(self, query):
        events = self.store.list_events(query)
        if any(event.key != query.key or (query.known_at is not None and event.observed_at > query.known_at)
               for event in events):
            self.violation("fact/source readout differs from requested scope")
        return events


class MemoryProvider(Protocol):
    name: str

    def index(self, project_id: str, known_at: object | None = None) -> dict[str, Any]: ...

    def search(self, project_id: str, text: str, as_of: object, known_at: object | None = None,
               top_k: int = 3, min_cosine: float = 0.55) -> dict[str, Any]: ...

    def safe_metadata(self) -> dict[str, Any]: ...

    def close(self) -> None: ...


def scope(project_id: str, known_at: object | None = None) -> tuple[str, datetime | None]:
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("project_id must be a nonempty string")
    return project_id.strip(), None if known_at is None else parse_timestamp(known_at, allow_date=True)


def request(project_id: str, text: str, as_of: object, known_at: object | None,
            top_k: int, min_cosine: float) -> tuple[str, str, datetime, datetime | None]:
    project_id, known_at = scope(project_id, known_at)
    # Mem0's public OpenAI embedder replaces LF before HTTP. Apply exactly this
    # normalization to every comparison arm, so the model receives equal input.
    if not isinstance(text, str) or not text.strip():
        raise ValueError("query must be a nonempty string")
    text = text.strip().replace("\n", " ")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
        raise ValueError("top_k must be an integer between 1 and 100")
    if (isinstance(min_cosine, bool) or not isinstance(min_cosine, Real)
            or not math.isfinite(min_cosine) or not 0 <= min_cosine < 1):
        raise ValueError("min_cosine must be finite and between 0 (inclusive) and 1 (exclusive)")
    query = MemoryQuery(project_id=project_id, predicate="comparison-search",
                        as_of=as_of, known_at=known_at)
    return project_id, text, query.as_of, known_at


def embedding_metadata(embedder: object) -> dict[str, Any]:
    method = getattr(embedder, "safe_metadata", None)
    if callable(method):
        return method()
    return {"fingerprint": getattr(embedder, "fingerprint", None),
            "request_count": getattr(embedder, "request_count", None),
            "usage": dict(getattr(embedder, "usage", {}))}
