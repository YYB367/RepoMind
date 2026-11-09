"""Explicit evidence review backed by the existing SQLite event ledger."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Literal

from pydantic import Field, field_validator

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import Contract, Event, Text, parse_timestamp
from repomind.intelligence.models import ExtractedMemory, SourceMessage

MAX_RECORD_BYTES = 4 * 1024 * 1024
REVIEW_TYPES = ("declare", "plan", "complete")


class Artifact(Contract):
    kind: Literal["file", "git"]
    path: Text
    commit: str | None = None
    sha256: str
    recorded_at: datetime

    @field_validator("recorded_at", mode="before")
    @classmethod
    def explicit_time(cls, value):
        return parse_timestamp(value)


class ReviewCandidate(Contract):
    candidate_id: str
    draft: Event
    artifact: Artifact
    quote: str
    status: Literal["pending", "confirmed", "rejected"]
    revision: int = Field(ge=1)
    reviewed_at: datetime | None = None
    event_id: str | None = None
    rationale: str | None = None


def read_record(path: Path, *, commit: str | None, repo: Path,
                recorded_at: str | None, quote: str) -> Artifact:
    """Read just the explicitly named record and validate the selected quote."""
    if not quote.strip() or len(quote) > 4000:
        raise ValueError("select a nonempty source quote of at most 4000 characters")
    if commit is None:
        if recorded_at is None:
            raise ValueError("a local file requires --recorded-at with an explicit time zone")
        when = parse_timestamp(recorded_at)
        with path.open("rb") as stream:
            raw = stream.read(MAX_RECORD_BYTES + 1)
    else:
        if not re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit):
            raise ValueError("--commit requires a full Git commit object ID")
        if recorded_at is not None:
            raise ValueError("Git evidence derives its recorded time from the commit")
        commit = commit.lower()
        relative = PurePosixPath(path.as_posix())
        if (relative.is_absolute() or ".." in relative.parts or not relative.parts
                or re.search(r"[:\\\x00-\x1f]", relative.as_posix())):
            raise ValueError("Git evidence requires a repository-relative path")

        def git(*arguments):
            result = subprocess.run(
                ["git", "-c", "safe.directory=" + str(repo.resolve()), "--no-replace-objects", "-C", str(repo), *arguments],
                capture_output=True, timeout=10,
            )
            if result.returncode:
                raise ValueError("cannot read the selected Git commit or file")
            return result.stdout

        try:
            if git("cat-file", "-t", commit).strip() != b"commit":
                raise ValueError("selected Git object is not a commit")
            blob = f"{commit}:{relative.as_posix()}"
            if int(git("cat-file", "-s", blob)) > MAX_RECORD_BYTES:
                raise ValueError("source record exceeds the 4 MiB limit")
            raw = git("cat-file", "blob", blob)
            when = parse_timestamp(git("show", "-s", "--no-show-signature", "--format=%cI", commit).decode().strip())
        except subprocess.TimeoutExpired:
            raise ValueError("reading the Git record timed out") from None
    if len(raw) > MAX_RECORD_BYTES:
        raise ValueError("source record exceeds the 4 MiB limit")
    if quote not in raw.decode("utf-8-sig"):
        raise ValueError("quote must be an exact substring of the selected UTF-8 record")
    locator = relative.as_posix() if commit else path.resolve().as_posix()
    return Artifact(kind="git" if commit else "file", path=locator, commit=commit,
                    sha256=hashlib.sha256(raw).hexdigest(), recorded_at=when)


class ReviewQueue:
    def __init__(self, store: SQLiteMemoryStore, *, initialize: bool = True):
        self.store = store
        self.db = store.connection
        if not initialize:
            return
        self.db.execute("""CREATE TABLE IF NOT EXISTS memory_review_candidates (
            candidate_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending','confirmed','rejected')),
            event_id TEXT UNIQUE REFERENCES events(event_id),
            candidate_json TEXT NOT NULL
        )""")
        self.db.execute('CREATE TABLE IF NOT EXISTS memory_review_notes (candidate_id TEXT PRIMARY KEY, rationale TEXT NOT NULL)')

    def _with_note(self, candidate):
        if not self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_review_notes'").fetchone():
            return candidate
        row=self.db.execute('SELECT rationale FROM memory_review_notes WHERE candidate_id=?',(candidate.candidate_id,)).fetchone()
        return candidate if row is None else candidate.model_copy(update={'rationale':row[0]})

    def _save(self, candidate: ReviewCandidate) -> None:
        self.db.execute(
            "UPDATE memory_review_candidates SET status=?,event_id=?,candidate_json=? WHERE candidate_id=?",
            (candidate.status, candidate.event_id, candidate.model_dump_json(exclude={'rationale'}), candidate.candidate_id),
        )

    def propose(self, *, artifact: Artifact, quote: str, project_id: str, subject: str,
                predicate: str, value: str, event_type: str, effective_at: str | None, rationale: str | None = None):
        # The source bytes and original fact key identify the same proposal even after an edit.
        identity = [item.strip() for item in (project_id, subject, predicate)] + [artifact.sha256]
        fingerprint = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()
        candidate_id = "review-" + fingerprint
        draft = self._draft(
            event_id=candidate_id, source_id="review-source-" + fingerprint, project_id=project_id,
            subject=subject, predicate=predicate, value=value, event_type=event_type,
            observed_at=artifact.recorded_at, effective_at=effective_at,
        )
        candidate = ReviewCandidate(candidate_id=candidate_id, draft=draft, artifact=artifact,
                                    quote=quote, status="pending", revision=1, rationale=rationale)
        with self.store.write_transaction():
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO memory_review_candidates VALUES (?, ?, 'pending', NULL, ?)",
                (candidate_id, draft.project_id, candidate.model_dump_json(exclude={'rationale'})),
            )
            if cursor.rowcount==1 and rationale:
                self.db.execute('INSERT INTO memory_review_notes VALUES (?,?)',(candidate_id,rationale))
            return self.show(draft.project_id, candidate_id), cursor.rowcount == 1

    @staticmethod
    def _draft(**fields) -> Event:
        if fields["event_type"] not in REVIEW_TYPES:
            raise ValueError("review supports declare, plan and complete")
        return Event.model_validate(fields)

    def list(self, project_id: str, status: str | None) -> list[ReviewCandidate]:
        rows = self.db.execute(
            """SELECT candidate_json FROM memory_review_candidates
               WHERE project_id=? AND (? IS NULL OR status=?) ORDER BY candidate_id""",
            (project_id, status, status),
        )
        return [self._with_note(ReviewCandidate.model_validate_json(row[0])) for row in rows]

    def show(self, project_id: str, candidate_id: str) -> ReviewCandidate:
        row = self.db.execute(
            "SELECT candidate_json FROM memory_review_candidates WHERE project_id=? AND candidate_id=?",
            (project_id, candidate_id),
        ).fetchone()
        if row is None:
            raise ValueError("candidate not found in this project")
        return self._with_note(ReviewCandidate.model_validate_json(row[0]))

    def edit(self, project_id: str, candidate_id: str, revision: int, **changes) -> ReviewCandidate:
        if not changes or not changes.keys() <= {"value", "event_type", "effective_at"}:
            raise ValueError("edit requires a value, event type or effective time")
        with self.store.write_transaction():
            old = self._at_revision(project_id, candidate_id, revision)
            if old.status != "pending":
                raise ValueError("only pending candidates can be edited")
            draft = self._draft(**(old.draft.model_dump() | changes))
            if draft == old.draft:
                return old
            updated = old.model_copy(update={"draft": draft, "revision": old.revision + 1})
            self._save(updated)
            return updated

    def _at_revision(self, project_id: str, candidate_id: str, revision: int) -> ReviewCandidate:
        candidate = self.show(project_id, candidate_id)
        if candidate.revision != revision:
            raise ValueError("candidate revision has changed; show it again before reviewing")
        return candidate

    def decide(self, project_id: str, candidate_id: str, revision: int, *,
               decision: Literal["confirmed", "rejected"]) -> ReviewCandidate:
        if decision not in {"confirmed", "rejected"}:
            raise ValueError("unsupported review decision")
        with self.store.write_transaction():
            candidate = self._at_revision(project_id, candidate_id, revision)
            if candidate.status == decision:
                return candidate
            if candidate.status != "pending":
                raise ValueError("candidate already has a final review decision")
            now = datetime.now(timezone.utc)
            event_id = None
            if decision == "confirmed":
                if now < candidate.artifact.recorded_at:
                    raise ValueError("cannot confirm evidence whose recorded time is in the future")
                event = Event.model_validate(candidate.draft.model_dump() | {"observed_at": now})
                source = SourceMessage(project_id=event.project_id, source_id=event.source_id,
                                       observed_at=now, text=candidate.quote)
                memory = ExtractedMemory(events=[event], source=source, provider="explicit-review",
                                         evidence_by_event={event.event_id: candidate.quote})
                self.store._append_records([(event, event.model_dump_json(), 1)], "candidate review", [memory])
                event_id = event.event_id
            updated = candidate.model_copy(update={"status": decision, "reviewed_at": now, "event_id": event_id})
            self._save(updated)
            return updated


def review_artifact(store: SQLiteMemoryStore, project_id: str, source_id: str) -> dict | None:
    if not source_id.startswith("review-source-"):
        return None
    db = store.connection
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_review_candidates'").fetchone():
        return None
    row = db.execute(
        """SELECT candidate_json FROM memory_review_candidates
           WHERE project_id=? AND candidate_id=? AND status='confirmed'""",
        (project_id, source_id.replace("review-source-", "review-", 1)),
    ).fetchone()
    return None if row is None else ReviewCandidate.model_validate_json(row[0]).artifact.model_dump(mode="json")
