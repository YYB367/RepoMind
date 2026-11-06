"""Append-only event ledger with serialized, all-or-nothing imports."""

from contextlib import contextmanager
import json
import math
from pathlib import Path
import sqlite3

from repomind.domain.models import Event, ImportResult, MemoryQuery
from repomind.memory.store import ImportValidationError, read_events, validate_links


class SQLiteMemoryStore:
    def __init__(self, path: str | Path, *, read_only: bool = False):
        filename = Path(path).resolve().as_uri() + "?mode=ro" if read_only else str(path)
        self.connection = sqlite3.connect(filename, uri=read_only, isolation_level=None, timeout=10)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        if read_only:
            return
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
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
            self.connection.execute("""CREATE TABLE IF NOT EXISTS nl_sources (
                project_id TEXT NOT NULL, source_id TEXT NOT NULL,
                content_hash TEXT NOT NULL, source_json TEXT NOT NULL,
                PRIMARY KEY (project_id, source_id)
            )""")
            self.connection.execute("""CREATE TABLE IF NOT EXISTS extraction_provenance (
                event_id TEXT PRIMARY KEY REFERENCES events(event_id),
                project_id TEXT NOT NULL, source_id TEXT NOT NULL,
                evidence_text TEXT NOT NULL, provider TEXT NOT NULL,
                FOREIGN KEY (project_id, source_id) REFERENCES nl_sources(project_id, source_id)
            )""")
            self.connection.execute("""CREATE TABLE IF NOT EXISTS memory_vectors (
                project_id TEXT NOT NULL, subject TEXT NOT NULL, predicate TEXT NOT NULL,
                fingerprint TEXT NOT NULL, text_hash TEXT NOT NULL,
                vector_json TEXT NOT NULL, dimensions INTEGER NOT NULL,
                PRIMARY KEY (project_id, subject, predicate, fingerprint, text_hash)
            )""")
            self.connection.execute("PRAGMA user_version=2")
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
        return self._import_records(read_events(path), str(path))

    def import_events(self, events: list[Event]) -> ImportResult:
        records = [(event, event.model_dump_json(), number) for number, event in enumerate(events, 1)]
        return self._import_records(records, "validated events")

    def import_extractions(self, memories: list) -> ImportResult:
        records = [(event, event.model_dump_json(), number) for number, event in enumerate(
            (event for memory in memories for event in memory.events), 1)]
        return self._import_records(records, "extracted events", memories)

    @contextmanager
    def write_transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _import_records(self, records: list[tuple[Event, str, int]], path: str, memories: list | None = None) -> ImportResult:
        with self.write_transaction():
            return self._append_records(records, path, memories)

    def _append_records(self, records: list[tuple[Event, str, int]], path: str, memories: list | None = None) -> ImportResult:
        """Append validated events and evidence inside the caller's write transaction."""
        if not self.connection.in_transaction:
            raise RuntimeError("append requires a write transaction")
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
        for memory in memories or []:
            source = memory.source
            old = self.connection.execute(
                "SELECT content_hash FROM nl_sources WHERE project_id=? AND source_id=?",
                (source.project_id, source.source_id),
            ).fetchone()
            if old is not None and old[0] != source.content_hash:
                raise ImportValidationError("source_id already exists with different source content")
            self.connection.execute(
                "INSERT OR IGNORE INTO nl_sources VALUES (?, ?, ?, ?)",
                (source.project_id, source.source_id, source.content_hash, source.model_dump_json()),
            )
            for event in memory.events:
                quote = memory.evidence_by_event.get(event.event_id, "")
                if (event.project_id, event.source_id, event.observed_at) != (source.project_id, source.source_id, source.observed_at):
                    raise ImportValidationError("extracted event is outside its trusted source envelope")
                if not quote or quote not in source.text:
                    raise ImportValidationError("extracted event lacks an exact source quote")
                old_quote = self.connection.execute(
                    "SELECT evidence_text FROM extraction_provenance WHERE event_id=?", (event.event_id,)
                ).fetchone()
                if old_quote is not None and old_quote[0] != quote:
                    raise ImportValidationError("existing event has a different extraction quote")
                self.connection.execute(
                    "INSERT OR IGNORE INTO extraction_provenance VALUES (?, ?, ?, ?, ?)",
                    (event.event_id, source.project_id, source.source_id, quote, memory.provider),
                )
        return ImportResult(imported=len(pending), duplicates=duplicates)

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

    def project_events(self, project_id: str, known_at=None) -> list[Event]:
        rows = self.connection.execute(
            "SELECT canonical_json FROM events WHERE project_id=? ORDER BY event_id", (project_id,)
        )
        events = [Event.model_validate_json(row[0]) for row in rows]
        return [event for event in events if known_at is None or event.observed_at <= known_at]

    def get_source(self, project_id: str, source_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT source_json FROM nl_sources WHERE project_id=? AND source_id=?", (project_id, source_id)
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def get_provenance(self, event_id: str) -> dict | None:
        row = self.connection.execute("SELECT * FROM extraction_provenance WHERE event_id=?", (event_id,)).fetchone()
        return None if row is None else dict(row)

    @staticmethod
    def _validate_vector(vector: list) -> list[float]:
        if (not isinstance(vector, list) or not vector or len(vector) > 65536
            or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in vector)
            or not 0 < math.hypot(*vector) < math.inf):
            raise ValueError("vectors must have finite numeric components and nonzero finite norm")
        return [float(v) for v in vector]

    def put_vectors(self, records: list[dict]) -> None:
        validated = []
        dimensions = {}
        for record in records:
            vector = self._validate_vector(record["vector"])
            fingerprint = record["fingerprint"]
            if any(not isinstance(record[key], str) or not record[key].strip() for key in
                   ("project_id", "subject", "predicate", "fingerprint", "text_hash")):
                raise ValueError("vector cache keys must be nonempty strings")
            if fingerprint in dimensions and dimensions[fingerprint] != len(vector):
                raise ValueError("embedding model fingerprint has inconsistent dimensions")
            dimensions[fingerprint] = len(vector)
            validated.append((record, vector))
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            for fingerprint, size in dimensions.items():
                old_sizes = {row[0] for row in self.connection.execute(
                    "SELECT DISTINCT dimensions FROM memory_vectors WHERE fingerprint=?", (fingerprint,))}
                if old_sizes and old_sizes != {size}:
                    raise ValueError("embedding model fingerprint has inconsistent dimensions")
            for record, vector in validated:
                self.connection.execute("INSERT OR REPLACE INTO memory_vectors VALUES (?, ?, ?, ?, ?, ?, ?)",
                    tuple(record[key] for key in ("project_id", "subject", "predicate", "fingerprint", "text_hash"))
                    + (json.dumps(vector, allow_nan=False), len(vector)))
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def get_vector(self, project_id: str, subject: str, predicate: str, fingerprint: str, text_hash: str) -> list[float] | None:
        row = self.connection.execute("""SELECT vector_json, dimensions FROM memory_vectors
            WHERE project_id=? AND subject=? AND predicate=? AND fingerprint=? AND text_hash=?""",
            (project_id, subject, predicate, fingerprint, text_hash)).fetchone()
        if row is None:
            return None
        vector = self._validate_vector(json.loads(row[0]))
        if len(vector) != row[1]:
            raise ValueError("stored embedding dimension metadata is corrupt")
        return vector
