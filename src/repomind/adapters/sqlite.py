"""Append-only event ledger with serialized, all-or-nothing imports."""

import json
from pathlib import Path
import sqlite3

from repomind.domain.models import Event, ImportResult, MemoryQuery
from repomind.memory.store import ImportValidationError, read_events, validate_links


class SQLiteMemoryStore:
    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError(f"unsupported database schema version {version}")
            self.connection.execute("""CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                value TEXT NOT NULL,
                event_type TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                effective_at TEXT NOT NULL,
                source_id TEXT NOT NULL,
                supersedes_event_id TEXT,
                canonical_json TEXT NOT NULL,
                raw_json TEXT NOT NULL
            )""")
            self.connection.execute("""CREATE INDEX IF NOT EXISTS events_scope
                ON events(project_id, subject, predicate, observed_at)""")
            self.connection.execute("PRAGMA user_version=1")
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            self.connection.close()
            raise

    def __enter__(self) -> "SQLiteMemoryStore":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    @staticmethod
    def _canonical(event: Event) -> str:
        return json.dumps(event.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)

    def import_jsonl(self, path: str | Path) -> ImportResult:
        records = read_events(path)
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            existing = {
                row["event_id"]: Event.model_validate_json(row["canonical_json"])
                for row in self.connection.execute("SELECT event_id, canonical_json FROM events")
            }
            ledger = existing.copy()
            pending = []
            duplicates = 0
            for event, raw, number in records:
                if event.event_id in ledger:
                    if event != ledger[event.event_id]:
                        raise ImportValidationError(
                            f"{path}:{number}: event_id {event.event_id} already has different content"
                        )
                    duplicates += 1
                    continue
                ledger[event.event_id] = event
                pending.append((event, raw))
            try:
                validate_links(ledger)
            except ImportValidationError as exc:
                lines = ", ".join(f"{n}:{e.event_id}" for e, _, n in records)
                raise ImportValidationError(f"{path}: correction validation failed ({lines}): {exc}") from exc
            for event, raw in pending:
                data = event.model_dump(mode="json")
                columns = ("event_id", "project_id", "subject", "predicate", "value", "event_type",
                           "observed_at", "effective_at", "source_id", "supersedes_event_id")
                self.connection.execute(
                    "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    tuple(data[column] for column in columns) + (self._canonical(event), raw),
                )
            self.connection.commit()
            return ImportResult(imported=len(pending), duplicates=duplicates)
        except Exception:
            self.connection.rollback()
            raise

    def list_events(self, query: MemoryQuery) -> list[Event]:
        # Datetime strings serialize with optional fractions. Compare parsed times
        # below rather than relying on lexicographic SQLite ordering at boundaries.
        rows = self.connection.execute(
            "SELECT canonical_json FROM events WHERE project_id=? AND subject=? AND predicate=? ORDER BY event_id",
            query.key,
        )
        events = [Event.model_validate_json(row[0]) for row in rows]
        return [event for event in events if query.known_at is None or event.observed_at <= query.known_at]

    def get_event(self, event_id: str) -> Event | None:
        row = self.connection.execute("SELECT canonical_json FROM events WHERE event_id=?", (event_id,)).fetchone()
        return None if row is None else Event.model_validate_json(row[0])

    def count(self) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
