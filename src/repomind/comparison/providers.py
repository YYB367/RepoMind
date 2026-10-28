"""No-memory and native comparison arms; each runner owns an isolated ledger."""

from typing import Any

from repomind.comparison.base import ScopeViolationError, ScopedReadout, embedding_metadata, request, scope
from repomind.intelligence.search import HybridMemorySearch


class NoMemoryProvider:
    name = "no_memory"

    def __init__(self, store=None):
        # The baseline deliberately does not inspect the supplied history.
        self.scope_violation_count = 0

    def index(self, project_id: str, known_at: object | None = None) -> dict[str, Any]:
        project_id, known_at = scope(project_id, known_at)
        return {"project_id": project_id, "count": 0, "requested": 0, "cached": 0,
                "known_at": None if known_at is None else known_at.isoformat(), "provider": self.name}

    def search(self, project_id: str, text: str, as_of: object, known_at: object | None = None,
               top_k: int = 3, min_cosine: float = 0.55) -> dict[str, Any]:
        project_id, text, as_of, known_at = request(project_id, text, as_of, known_at, top_k, min_cosine)
        return {"project_id": project_id, "query": text, "mode": "no_memory", "provider": self.name,
                "as_of": as_of.isoformat(), "known_at": None if known_at is None else known_at.isoformat(),
                "top_k": top_k, "min_cosine": float(min_cosine), "indexed_documents": 0,
                "hits": [], "reason": "no_memory_baseline"}

    def safe_metadata(self) -> dict[str, Any]:
        return {"name": self.name, "embedding": None, "scope_violation_count": self.scope_violation_count,
                "strategy": "no history retrieval; empty evidence", "query_normalization": "strip and replace LF with space"}

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class NativeMemoryProvider:
    def __init__(self, store, embedder, mode: str = "semantic"):
        if mode not in {"semantic", "hybrid"}:
            raise ValueError("native comparison mode must be semantic or hybrid")
        self.mode, self.embedder = mode, embedder
        self.name = "repomind_" + mode
        self.scope_violation_count = 0
        self.retriever = HybridMemorySearch(ScopedReadout(store, self._violation), embedder)

    def _violation(self, message):
        self.scope_violation_count += 1
        raise ScopeViolationError(self.name + " scope violation: " + message)

    def index(self, project_id: str, known_at: object | None = None) -> dict[str, Any]:
        return self.retriever.index(project_id, known_at=known_at) | {"provider": self.name}

    def search(self, project_id: str, text: str, as_of: object, known_at: object | None = None,
               top_k: int = 3, min_cosine: float = 0.55) -> dict[str, Any]:
        project_id, text, as_of, known_at = request(project_id, text, as_of, known_at, top_k, min_cosine)
        return self.retriever.search(project_id, text, as_of, known_at=known_at, top_k=top_k,
                                     mode=self.mode, min_cosine=min_cosine) | {"provider": self.name}

    def safe_metadata(self) -> dict[str, Any]:
        return {"name": self.name, "mode": self.mode, "embedding": embedding_metadata(self.embedder),
                "scope_violation_count": self.scope_violation_count,
                "strategy": "property documents; shared V1 resolver; cosine" + (" plus lexical RRF k=60" if self.mode == "hybrid" else ""),
                "query_normalization": "strip and replace LF with space", "storage_ownership": "runner owns isolated SQLite ledger"}

    def close(self) -> None:
        # The runner owns the ledger and provider client, and closes them.
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
