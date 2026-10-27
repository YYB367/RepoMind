"""Bind model candidates to trusted provenance before ledger insertion."""

from __future__ import annotations

import hashlib
import json
from typing import Protocol

from repomind.domain.models import Event
from repomind.intelligence.models import ExtractedMemory, ExtractionBatch, SourceMessage


class ExtractionProvider(Protocol):
    name: str

    def extract(self, source: SourceMessage, context: list[Event]) -> ExtractionBatch: ...


class Extractor:
    def __init__(self, provider: ExtractionProvider):
        self.provider = provider

    def extract(self, source: SourceMessage, context: list[Event] | None = None) -> ExtractedMemory:
        # Revalidation protects callers that pass model_construct/model_copy
        # instances; provider output never owns the trusted project/source IDs.
        source = SourceMessage.model_validate(source.model_dump())
        context = list(context or [])
        if any(event.project_id != source.project_id for event in context):
            raise ValueError("extraction context must contain only the source project")
        by_id = {event.event_id: event for event in context}
        if len(by_id) != len(context):
            raise ValueError("extraction context has duplicate event IDs")
        response = self.provider.extract(source, context)
        batch = ExtractionBatch.model_validate(response.model_dump() if isinstance(response, ExtractionBatch) else response)
        events: dict[str, Event] = {}
        evidence: dict[str, str] = {}
        for fact in batch.facts:
            if fact.evidence_text not in source.text:
                raise ValueError("candidate evidence_text is not an exact source substring")
            effective_at = fact.effective_at
            if fact.event_type == "correct":
                target = by_id.get(fact.supersedes_event_id)
                if target is None:
                    raise ValueError("correction target is absent from existing context")
                if target.event_type == "plan":
                    raise ValueError("a plan cannot be corrected into an implemented fact")
                if target.key != (source.project_id, fact.subject, fact.predicate):
                    raise ValueError("correction target has a different fact scope")
                if effective_at is not None and effective_at != target.effective_at:
                    raise ValueError("correction must retain target effective_at")
                if target.observed_at > source.observed_at:
                    raise ValueError("correction cannot be observed before its target")
                effective_at = target.effective_at
            normalized = fact.model_dump(mode="json")
            # Resolve omitted effective time before hashing. Fact order and
            # duplicate entries do not influence stable generated event IDs.
            normalized["effective_at"] = (effective_at or source.observed_at).isoformat()
            canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            event_id = "nl-" + hashlib.sha256((source.content_hash + canonical).encode("utf-8")).hexdigest()[:32]
            event = Event(
                event_id=event_id,
                project_id=source.project_id,
                source_id=source.source_id,
                observed_at=source.observed_at,
                subject=fact.subject,
                predicate=fact.predicate,
                value=fact.value,
                event_type=fact.event_type,
                effective_at=effective_at,
                supersedes_event_id=fact.supersedes_event_id,
            )
            events[event_id] = event
            evidence[event_id] = fact.evidence_text
        ordered = sorted(events)
        return ExtractedMemory(events=[events[key] for key in ordered], evidence_by_event={key: evidence[key] for key in ordered}, source=source, provider=self.provider.name, abstain_reason=batch.abstain_reason)
