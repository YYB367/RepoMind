"""Prepare auditable candidates; only the CLI's explicit apply writes the ledger."""

import json
from pathlib import Path

from repomind.intelligence.extraction import Extractor
from repomind.intelligence.models import SourceMessage
from repomind.intelligence.models import ExtractedMemory
from repomind.memory.store import _unique_keys


def read_sources(path: str | Path) -> list[SourceMessage]:
    sources, seen = [], {}
    path = Path(path)
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            source = SourceMessage.model_validate(json.loads(line, object_pairs_hook=_unique_keys))
            key = source.project_id, source.source_id
            if key in seen and seen[key] != source.content_hash:
                raise ValueError("source_id is reused with different content in the input batch")
            seen[key] = source.content_hash
        except ValueError as exc:
            raise ValueError(f"{path}:{number}: {exc}") from exc
        sources.append(source)
    if not sources:
        raise ValueError(f"{path}: source input is empty")
    return sources


def prepare_ingestion(store, sources: list[SourceMessage], provider) -> list:
    extractor = Extractor(provider)
    contexts, memories, prepared_sources = {}, [], {}
    for source in sources:
        if source.content_hash in prepared_sources:
            memories.append(prepared_sources[source.content_hash])
            continue
        old_source = store.get_source(source.project_id, source.source_id)
        if old_source is not None:
            old = SourceMessage.model_validate(old_source)
            if old.content_hash != source.content_hash:
                raise ValueError("source_id already exists with different source content")
        if source.project_id not in contexts:
            contexts[source.project_id] = {event.event_id: event for event in store.project_events(source.project_id)}
        context = contexts[source.project_id]
        if old_source is not None:
            # Reusing an immutable source must not invoke a stochastic model
            # again and create a second set of IDs from differently sized quotes.
            events, quotes, providers = [], {}, set()
            for event in context.values():
                if event.source_id == source.source_id:
                    provenance = store.get_provenance(event.event_id)
                    if provenance is not None:
                        events.append(event)
                        quotes[event.event_id] = provenance["evidence_text"]
                        providers.add(provenance["provider"])
            memory = ExtractedMemory(source=source, events=sorted(events, key=lambda event: event.event_id),
                evidence_by_event=quotes, provider="stored-source-cache:" + ",".join(sorted(providers)),
                abstain_reason=None if events else "Previously processed source has no extracted facts.")
        else:
            memory = extractor.extract(source, list(context.values()))
        for event in memory.events:
            if event.event_id in context and context[event.event_id] != event:
                raise ValueError("extracted event_id already exists with different content")
            context[event.event_id] = event
        memories.append(memory)
        prepared_sources[source.content_hash] = memory
    return memories


def validate_output_paths(output: str | Path, inputs: list[Path]) -> None:
    output = Path(output)
    audit_path = output.with_suffix(".audit.json")
    input_paths = {path.resolve() for path in inputs}
    if output.resolve() in input_paths or audit_path.resolve() in input_paths:
        raise ValueError("candidate artifacts must not overwrite source inputs or replay data")
    if output.name == ".env" or output.name.startswith(".env."):
        raise ValueError("candidate artifacts must not overwrite configuration files")


def write_candidate_bundle(memories: list, output: str | Path, inputs: list[Path]) -> dict:
    validate_output_paths(output, inputs)
    output = Path(output)
    audit_path = output.with_suffix(".audit.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    events = {event.event_id: event for memory in memories for event in memory.events}
    output.write_text("".join(event.model_dump_json() + "\n" for event in events.values()), encoding="utf-8")
    audit = {
        "stage_goal": "V1.1: grounded candidate extraction with preserved temporal facts",
        "purpose": "candidate audit; the CLI apply receipt separately reports ledger commit status",
        "memories": [memory.model_dump(mode="json") for memory in memories],
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"events": str(output), "audit": str(audit_path), "event_count": len(events)}
