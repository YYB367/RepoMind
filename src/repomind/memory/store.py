"""JSONL validation before atomic persistence."""

import json
from pathlib import Path

from pydantic import ValidationError

from repomind.domain.models import Event


class ImportValidationError(ValueError):
    """A diagnosable import error; the entire batch is rejected."""


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_events(path: str | Path) -> list[tuple[Event, str, int]]:
    path = Path(path)
    events = []
    with path.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line, object_pairs_hook=_unique_keys)
                event = Event.model_validate(payload)
            except (ValueError, ValidationError) as exc:
                raise ImportValidationError(f"{path}:{number}: {exc}") from exc
            events.append((event, line.rstrip("\r\n"), number))
    return events


def validate_links(events: dict[str, Event]) -> None:
    """Validate complete ledger links, independent of batch ordering."""
    for event in events.values():
        target_id = event.supersedes_event_id
        if target_id is None:
            continue
        target = events.get(target_id)
        if target is None:
            raise ImportValidationError(f"{event.event_id}: missing correction target {target_id}")
        if target.event_type == "plan":
            raise ImportValidationError(f"{event.event_id}: cannot correct a plan into a fact")
        if target.key != event.key:
            raise ImportValidationError(f"{event.event_id}: correction target has a different scope")
        if target.effective_at != event.effective_at:
            raise ImportValidationError(f"{event.event_id}: correction must retain target effective_at")
        if target.observed_at > event.observed_at:
            raise ImportValidationError(f"{event.event_id}: correction observed before its target")
    finished = set()
    for start in events:
        visiting = set()
        current = start
        while current not in finished:
            if current in visiting:
                raise ImportValidationError(f"{start}: correction cycle")
            visiting.add(current)
            target_id = events[current].supersedes_event_id
            if target_id is None:
                break
            current = target_id
        finished.update(visiting)
