"""Explicit event time, fact time, and evidence contracts."""

from datetime import date, datetime, time, timezone
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]


def parse_timestamp(value: object, *, allow_date: bool = False) -> datetime:
    """Reject implicit local time and Unix timestamps; normalize explicit zones."""
    if isinstance(value, datetime):
        parsed = value
    elif allow_date and isinstance(value, date):
        parsed = datetime.combine(value, time.max, timezone.utc)
    elif isinstance(value, str):
        if allow_date and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            parsed = datetime.combine(date.fromisoformat(value), time.max, timezone.utc)
        else:
            if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", value):
                raise ValueError("expected ISO 8601 datetime with explicit timezone")
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("expected ISO 8601 string or timezone-aware datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime must include timezone (Z or UTC offset)")
    try:
        return parsed.astimezone(timezone.utc)
    except OverflowError as exc:
        raise ValueError("datetime outside supported UTC range") from exc


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Event(Contract):
    event_id: Text
    project_id: Text
    subject: Text
    predicate: Text
    value: Text
    event_type: Literal["declare", "plan", "complete", "correct"]
    observed_at: datetime
    effective_at: datetime | None = None
    source_id: Text
    supersedes_event_id: Text | None = None

    @field_validator("observed_at", "effective_at", mode="before")
    @classmethod
    def validate_timestamp(cls, value: object) -> datetime | None:
        return None if value is None else parse_timestamp(value)

    @model_validator(mode="after")
    def validate_event(self) -> "Event":
        if self.effective_at is None:
            object.__setattr__(self, "effective_at", self.observed_at)
        if self.event_type != "plan" and self.effective_at > self.observed_at:
            raise ValueError("actual fact effective_at cannot be later than observed_at")
        if self.event_type == "correct":
            if not self.supersedes_event_id:
                raise ValueError("correct requires supersedes_event_id")
            if self.supersedes_event_id == self.event_id:
                raise ValueError("event cannot supersede itself")
        elif self.supersedes_event_id is not None:
            raise ValueError("only correct events may specify supersedes_event_id")
        return self

    @property
    def key(self) -> tuple[str, str, str]:
        return self.project_id, self.subject, self.predicate


class MemoryQuery(Contract):
    project_id: Text
    subject: Text = "project"
    predicate: Text
    as_of: datetime
    known_at: datetime | None = None

    @field_validator("as_of", "known_at", mode="before")
    @classmethod
    def validate_query_time(cls, value: object) -> datetime | None:
        return None if value is None else parse_timestamp(value, allow_date=True)

    @property
    def key(self) -> tuple[str, str, str]:
        return self.project_id, self.subject, self.predicate


class QueryResult(Contract):
    status: Literal["ok", "unknown", "insufficient_evidence"]
    value: Text | None = None
    evidence: list[Event] = Field(default_factory=list)
    reason: str
    considered_event_ids: list[str] = Field(default_factory=list)
    plan_event_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_answer(self) -> "QueryResult":
        if self.status == "ok" and (self.value is None or not self.evidence):
            raise ValueError("ok requires a value and supporting evidence")
        if self.status != "ok" and self.value is not None:
            raise ValueError("refusal cannot have a definite value")
        if self.status == "unknown" and self.evidence:
            raise ValueError("unknown cannot cite supporting facts")
        return self


class ImportResult(Contract):
    imported: int
    duplicates: int
