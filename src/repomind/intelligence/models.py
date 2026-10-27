"""Trusted source envelopes and untrusted model candidate contracts."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from repomind.domain.models import Contract, Event, Text, parse_timestamp

VerbatimText = Annotated[str, StringConstraints(strict=True, min_length=1)]


class SourceMessage(Contract):
    project_id: Text
    source_id: Text
    observed_at: datetime
    text: Annotated[VerbatimText, Field(max_length=200_000)]

    @field_validator("observed_at", mode="before")
    @classmethod
    def explicit_time(cls, value: object) -> datetime:
        return parse_timestamp(value)

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source text must contain non-whitespace characters")
        return value

    @property
    def content_hash(self) -> str:
        """Hash the entire trusted envelope, not merely the free text."""
        canonical = json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class CandidateFact(Contract):
    subject: Text
    predicate: Text
    value: Text
    event_type: Literal["declare", "plan", "complete", "correct"]
    effective_at: datetime | None = None
    supersedes_event_id: Text | None = None
    evidence_text: VerbatimText

    @field_validator("effective_at", mode="before")
    @classmethod
    def explicit_effective_time(cls, value: object) -> datetime | None:
        return None if value is None else parse_timestamp(value)

    @field_validator("evidence_text")
    @classmethod
    def meaningful_quote(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence_text must contain non-whitespace characters")
        return value

    @model_validator(mode="after")
    def correction_target(self) -> "CandidateFact":
        if self.event_type == "correct" and not self.supersedes_event_id:
            raise ValueError("a correction needs an explicit supersedes_event_id")
        if self.event_type != "correct" and self.supersedes_event_id is not None:
            raise ValueError("only a correction may specify supersedes_event_id")
        return self


class ExtractionBatch(Contract):
    facts: list[CandidateFact]
    abstain_reason: Text | None = None

    @model_validator(mode="after")
    def explicit_abstention(self) -> "ExtractionBatch":
        if not self.facts and not self.abstain_reason:
            raise ValueError("an empty facts list requires abstain_reason")
        if self.facts and self.abstain_reason is not None:
            raise ValueError("facts and abstain_reason are mutually exclusive")
        return self


class ExtractedMemory(Contract):
    events: list[Event]
    evidence_by_event: dict[str, str]
    source: SourceMessage
    provider: Text
    abstain_reason: Text | None = None

    @model_validator(mode="after")
    def source_binding(self) -> "ExtractedMemory":
        ids = [event.event_id for event in self.events]
        if len(ids) != len(set(ids)) or set(ids) != set(self.evidence_by_event):
            raise ValueError("events and evidence_by_event must have exactly the same unique IDs")
        for event in self.events:
            if (event.project_id, event.source_id, event.observed_at) != (self.source.project_id, self.source.source_id, self.source.observed_at):
                raise ValueError("event scope/source/time must be bound to the trusted source")
            quote = self.evidence_by_event[event.event_id]
            if not isinstance(quote, str) or not quote.strip() or quote not in self.source.text:
                raise ValueError("event evidence must be an exact nonempty source substring")
        if not self.events and not self.abstain_reason:
            raise ValueError("empty extracted memory requires abstain_reason")
        if self.events and self.abstain_reason is not None:
            raise ValueError("events and abstain_reason are mutually exclusive")
        return self
