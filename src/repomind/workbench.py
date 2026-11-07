"""Read projections for the workbench; writes use the original review service."""
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import MemoryQuery
from repomind.memory.resolver import MemoryResolver
from repomind.memory.review import ReviewQueue, review_artifact


def has_reviews(store):
    return bool(store.connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_review_candidates'"
    ).fetchone())


def page(rows, offset, limit):
    return {"items": rows[offset:offset + limit], "total": len(rows), "offset": offset, "limit": limit}


class Workbench:
    def __init__(self, database: Path):
        self.database = database

    def projects(self):
        if not self.database.is_file():
            return []
        with SQLiteMemoryStore(self.database, read_only=True) as store:
            store.connection.execute("BEGIN")
            names = {row[0] for row in store.connection.execute("SELECT DISTINCT project_id FROM events")}
            if has_reviews(store):
                names.update(row[0] for row in store.connection.execute(
                    "SELECT DISTINCT project_id FROM memory_review_candidates"))
            return sorted(names)

    def candidates(self, project, *, status="pending", q="", offset=0, limit=50):
        rows = []
        counts = {name: 0 for name in ("pending", "confirmed", "rejected")}
        if self.database.is_file():
            with SQLiteMemoryStore(self.database, read_only=True) as store:
                store.connection.execute("BEGIN")
                if has_reviews(store):
                    for row in ReviewQueue(store, initialize=False).list(project, None):
                        counts[row.status] += 1
                        text = f"{row.draft.subject} {row.draft.predicate} {row.draft.value} {row.quote}"
                        if (status == "all" or row.status == status) and q.casefold() in text.casefold():
                            rows.append(row.model_dump(mode="json"))
        rows.sort(key=lambda row: (row["artifact"]["recorded_at"], row["candidate_id"]), reverse=True)
        return page(rows, offset, limit) | {"counts": counts}

    def memories(self, project, *, q="", as_of=None, known_at=None, offset=0, limit=50):
        now = datetime.now(timezone.utc)
        # Validate dates even for an empty ledger/project.
        clock = MemoryQuery(project_id=project, predicate="_clock", as_of=as_of or now,
                            known_at=known_at or now)
        rows = []
        if self.database.is_file():
            with SQLiteMemoryStore(self.database, read_only=True) as store:
                store.connection.execute("BEGIN")
                groups = defaultdict(list)
                for event in store.project_events(project, clock.known_at):
                    groups[event.key].append(event)
                for (_, subject, predicate), events in sorted(groups.items()):
                    query = MemoryQuery(project_id=project, subject=subject, predicate=predicate,
                                        as_of=clock.as_of, known_at=clock.known_at)
                    answer = MemoryResolver().resolve(query, events)
                    plans = [event for event in events if event.event_id in answer.plan_event_ids]
                    evidence = answer.evidence or plans
                    # A future fact alone is not a memory on the selected date.
                    if not evidence:
                        continue
                    text = f"{subject} {predicate} " + " ".join(event.value for event in evidence)
                    if q.casefold() not in text.casefold():
                        continue
                    sources = []
                    for event in evidence:
                        sources.append({
                            "event": event.model_dump(mode="json"),
                            "record": store.get_source(project, event.source_id),
                            "provenance": store.get_provenance(event.event_id),
                            "artifact": review_artifact(store, project, event.source_id),
                        })
                    rows.append({"subject": subject, "field": predicate,
                                 **answer.model_dump(mode="json"), "sources": sources})
        return page(rows, offset, limit) | {"as_of": clock.as_of.isoformat(),
                                           "known_at": clock.known_at.isoformat()}
