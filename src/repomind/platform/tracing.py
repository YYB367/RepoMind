"""Local synthetic-benchmark telemetry and append-only delivery receipts.

The JSONL outbox is single-writer across processes. Its lock also serializes
threads sharing one instance. Cloud delivery remains explicitly at-least-once.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
from typing import Any, Literal, Mapping

from pydantic import ConfigDict, Field, field_validator, model_validator

from repomind.domain.models import Contract, Text, parse_timestamp
from repomind.memory.store import _unique_keys

_SECRET_FIELDS = {"apikey", "api_key", "secret", "secret_key", "public_key", "authorization",
                  "password", "access_token", "refresh_token", "bearer_token", "cookie",
                  "client_secret", "env", "environment_variables", "context.env"}
_TOKEN_FIELDS = {"prompt_tokens", "completion_tokens", "input_tokens", "output_tokens", "total_tokens"}
_COST_FIELDS = {"cost", "cost_usd", "total_cost", "estimated_cost"}
_KEY_VALUE = re.compile(r"\b(?:sk|pk)-(?:proj-|lf-)?[A-Za-z0-9_-]{8,}\b", re.IGNORECASE)
_AUTH_VALUE = re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9+/=_-]{8,}", re.IGNORECASE)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _number(value: Any, *, name: str, nonnegative: bool = False) -> float:
    try:
        valid = type(value) in (int, float) and math.isfinite(value) and (not nonnegative or value >= 0)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite {'nonnegative ' if nonnegative else ''}number")
    return float(value)


def clean_payload(value: Any) -> Any:
    """Remove recognizable credentials and reject unsupported/nonfinite JSON.

    This is defense in depth, not a detector of arbitrary private natural
    language. Callers must explicitly label and authorize synthetic inputs.
    """
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("telemetry JSON numbers must be finite")
        return value
    if isinstance(value, str):
        return _AUTH_VALUE.sub(r"\1 [REDACTED]", _KEY_VALUE.sub("[REDACTED]", value))
    if isinstance(value, (list, tuple)):
        return [clean_payload(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("telemetry object keys must be strings")
            normalized = key.casefold().replace("-", "_")
            if (normalized in _SECRET_FIELDS or normalized.endswith(("_api_key", "_secret_key", "_password", ".env"))
                or _KEY_VALUE.search(key) or _AUTH_VALUE.search(key)):
                continue
            if item is not None and normalized in _TOKEN_FIELDS:
                if type(item) is not int or item < 0:
                    raise ValueError("token usage must contain nonnegative integer counts")
            if item is not None and normalized in _COST_FIELDS:
                _number(item, name="cost", nonnegative=True)
            result[key] = clean_payload(item)
        return result
    raise ValueError("telemetry payloads must contain JSON values only")


class TraceObservation(Contract):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    name: Text
    as_type: Literal["span", "generation"] = "span"
    input: Any = None
    output: Any = None
    elapsed_seconds: float | None = None
    model: Text | None = None
    usage_details: dict[str, int] | None = None
    cost_details: dict[str, float] | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "model")
    @classmethod
    def safe_label(cls, value: str | None) -> str | None:
        if value is not None and clean_payload(value) != value:
            raise ValueError("observation labels must not contain credentials")
        return value

    @field_validator("input", "output", "metadata", mode="before")
    @classmethod
    def safe_json(cls, value: Any) -> Any:
        return clean_payload(value)

    @field_validator("elapsed_seconds", mode="before")
    @classmethod
    def valid_elapsed(cls, value: Any) -> float | None:
        return None if value is None else _number(value, name="elapsed_seconds", nonnegative=True)

    @field_validator("started_at", "ended_at", mode="before")
    @classmethod
    def explicit_time(cls, value: Any) -> datetime | None:
        return None if value is None else parse_timestamp(value)

    @field_validator("usage_details", mode="before")
    @classmethod
    def actual_usage_only(cls, value: Any) -> Any:
        if value is not None and (not isinstance(value, dict) or any(not isinstance(key, str) or type(count) is not int or count < 0 for key, count in value.items())):
            raise ValueError("usage_details must contain actual nonnegative integer counts")
        if value is not None and clean_payload(value) != value:
            raise ValueError("usage_details names must not contain credential fields")
        return value

    @field_validator("cost_details", mode="before")
    @classmethod
    def actual_cost_only(cls, value: Any) -> Any:
        if value is not None:
            if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
                raise ValueError("cost_details must be a string-keyed object")
            if clean_payload(value) != value:
                raise ValueError("cost_details names must not contain credential fields")
            return {key: _number(amount, name="cost_details", nonnegative=True) for key, amount in value.items()}
        return None

    @model_validator(mode="after")
    def time_order(self) -> "TraceObservation":
        if self.started_at is not None and self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("observation ended_at must not precede started_at")
        return self


class TraceRecord(Contract):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    schema_version: Literal["1.2"] = "1.2"
    run_id: Text
    item_id: Text
    provider: Text
    project_id: Text
    stage: Text
    synthetic: bool
    input: Any = None
    output: Any = None
    expected_output: Any = None
    scores: dict[str, float] = Field(default_factory=dict)
    observations: list[TraceObservation] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("synthetic", mode="before")
    @classmethod
    def explicit_synthetic(cls, value: Any) -> bool:
        if type(value) is not bool:
            raise ValueError("synthetic must be an explicit boolean")
        return value

    @field_validator("run_id", "item_id", "provider", "project_id", "stage")
    @classmethod
    def safe_identity(cls, value: str) -> str:
        if clean_payload(value) != value:
            raise ValueError("trace identity fields must not contain credentials")
        return value

    @field_validator("input", "output", "expected_output", "metadata", mode="before")
    @classmethod
    def safe_json(cls, value: Any) -> Any:
        return clean_payload(value)

    @field_validator("scores", mode="before")
    @classmethod
    def finite_scores(cls, value: Any) -> dict[str, float]:
        if not isinstance(value, dict) or any(not isinstance(key, str) or not key.strip() for key in value):
            raise ValueError("scores must have nonempty string names")
        if any(clean_payload({name: None}) != {name: None} for name in value):
            raise ValueError("score names must not contain credential fields")
        return {name: _number(score, name="score") for name, score in value.items()}

    @property
    def trace_id(self) -> str:
        identity = [self.schema_version, self.run_id, self.item_id, self.provider, self.project_id, self.stage]
        return hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()[:32]

    @property
    def payload_sha256(self) -> str:
        return hashlib.sha256(canonical_json(self.model_dump(mode="json")).encode("utf-8")).hexdigest()


class TraceOutbox:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.receipts_path = Path(str(self.path) + ".status.jsonl")
        self._lock = threading.RLock()

    @staticmethod
    def _append_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical_json(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        values = []
        for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line, object_pairs_hook=_unique_keys)
                if not isinstance(value, dict):
                    raise ValueError("expected an object")
            except ValueError:
                raise ValueError(f"{path}:{number}: invalid/torn JSONL; preserve the file and repair explicitly") from None
            values.append(value)
        return values

    def records(self) -> list[TraceRecord]:
        with self._lock:
            found: dict[str, TraceRecord] = {}
            for wrapper in self._read_jsonl(self.path):
                record = TraceRecord.model_validate(wrapper.get("record"))
                if wrapper.get("trace_id") != record.trace_id or wrapper.get("payload_sha256") != record.payload_sha256:
                    raise ValueError("outbox trace identity or payload hash mismatch")
                old = found.get(record.trace_id)
                if old is not None and old.payload_sha256 != record.payload_sha256:
                    raise ValueError("outbox trace ID has conflicting payloads")
                found[record.trace_id] = record
            return list(found.values())

    def append(self, record: TraceRecord | Mapping[str, Any]) -> bool:
        record = TraceRecord.model_validate(record.model_dump() if isinstance(record, TraceRecord) else dict(record))
        with self._lock:
            old = next((item for item in self.records() if item.trace_id == record.trace_id), None)
            if old is not None:
                if old.payload_sha256 != record.payload_sha256:
                    raise ValueError("same trace ID cannot overwrite a different payload; use a new run_id")
                return False
            self._append_json(self.path, {"trace_id": record.trace_id, "payload_sha256": record.payload_sha256,
                                          "recorded_at": datetime.now(timezone.utc).isoformat(),
                                          "record": record.model_dump(mode="json")})
            return True

    def record(self, event: TraceRecord | Mapping[str, Any]) -> str:
        item = TraceRecord.model_validate(event.model_dump() if isinstance(event, TraceRecord) else dict(event))
        self.append(item)
        return item.trace_id

    def state(self, trace_id: str, target: str = "langfuse") -> dict[str, Any]:
        current = {"trace_id": trace_id, "target": target, "status": "pending", "attempts": 0, "details": {}}
        with self._lock:
            record = next((item for item in self.records() if item.trace_id == trace_id), None)
            for receipt in self._read_jsonl(self.receipts_path):
                if receipt.get("trace_id") == trace_id and receipt.get("target") == target:
                    if (record is None or receipt.get("payload_sha256") != record.payload_sha256
                        or receipt.get("status") not in {"pending", "sent_unconfirmed", "verified", "failed"}
                        or type(receipt.get("attempts")) is not int or receipt["attempts"] < 0):
                        raise ValueError("outbox receipt has invalid status/hash/attempts")
                    current = receipt
        return dict(current)

    def recorded_at(self, trace_id: str) -> datetime:
        for wrapper in self._read_jsonl(self.path):
            if wrapper.get("trace_id") == trace_id:
                if "recorded_at" not in wrapper:
                    return datetime(2020, 1, 1, tzinfo=timezone.utc)
                return parse_timestamp(wrapper["recorded_at"])
        raise ValueError("trace is absent from this outbox")

    def pending(self, target: str = "langfuse") -> list[TraceRecord]:
        return [record for record in self.records() if self.state(record.trace_id, target)["status"] != "verified"]

    def record_status(self, trace_id: str, status: str, details: dict[str, Any] | None = None, *, target: str = "langfuse") -> None:
        if status not in {"pending", "sent_unconfirmed", "verified", "failed"}:
            raise ValueError("unknown outbox delivery status")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("outbox receipt target must be nonempty")
        with self._lock:
            record = next((item for item in self.records() if item.trace_id == trace_id), None)
            if record is None:
                raise ValueError("cannot acknowledge a trace absent from the outbox")
            previous = self.state(trace_id, target)
            attempts = previous["attempts"]
            if status == "sent_unconfirmed" or (status == "failed" and previous["status"] != "sent_unconfirmed"):
                attempts += 1
            receipt = {"trace_id": trace_id, "payload_sha256": record.payload_sha256, "target": target,
                       "status": status, "attempts": attempts, "at": datetime.now(timezone.utc).isoformat(),
                       "details": clean_payload(details or {})}
            self._append_json(self.receipts_path, receipt)

    def sync(self, exporter: Any, **kwargs: Any) -> dict[str, Any]:
        return exporter.sync(self, **kwargs)
