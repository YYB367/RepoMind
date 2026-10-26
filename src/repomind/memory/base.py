"""The small store interface needed by the retriever."""

from typing import Protocol

from repomind.domain.models import Event, MemoryQuery


class MemoryStore(Protocol):
    def list_events(self, query: MemoryQuery) -> list[Event]: ...

    def get_event(self, event_id: str) -> Event | None: ...
