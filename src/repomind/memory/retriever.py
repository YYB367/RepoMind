"""Exact scoped retrieval followed by replaceable deterministic resolution."""

from repomind.domain.models import MemoryQuery, QueryResult
from repomind.memory.base import MemoryStore
from repomind.memory.resolver import MemoryResolver


class MemoryRetriever:
    def __init__(self, store: MemoryStore, resolver: MemoryResolver | None = None):
        self.store = store
        self.resolver = resolver or MemoryResolver()

    def query(self, query: MemoryQuery) -> QueryResult:
        return self.resolver.resolve(query, self.store.list_events(query))
