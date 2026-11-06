"""CLI commands for explicit review; policy lives in the review service."""
import argparse
from pathlib import Path

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.memory.review import REVIEW_TYPES, ReviewQueue, read_record


def add_review_parser(commands):
    review = commands.add_parser("review", help="Propose and review evidence-backed project memory")
    review.add_argument("--db", type=Path, default=argparse.SUPPRESS, help="SQLite ledger path")
    actions = review.add_subparsers(dest="review_action", required=True)
    propose = actions.add_parser("propose", help="Create a pending candidate from a verified source quote")
    propose.add_argument("record", type=Path)
    propose.add_argument("--commit", help="Full Git commit ID for the repository-relative record")
    propose.add_argument("--repo", type=Path, default=Path("."))
    propose.add_argument("--recorded-at", help="Timestamp with zone for a local file")
    propose.add_argument("--quote", required=True)
    propose.add_argument("--subject", default="project")
    propose.add_argument("--field", required=True)
    propose.add_argument("--value", required=True)
    propose.add_argument("--event-type", choices=REVIEW_TYPES, required=True)
    propose.add_argument("--effective-at")
    listing = actions.add_parser("list", help="List candidates scoped to a project")
    listing.add_argument("--status", choices=("pending", "confirmed", "rejected"))
    for name in ("show", "edit", "confirm", "reject"):
        operation = actions.add_parser(name)
        operation.add_argument("candidate_id")
        if name != "show":
            operation.add_argument("--revision", required=True, type=int)
        if name == "edit":
            operation.add_argument("--value")
            operation.add_argument("--event-type", choices=REVIEW_TYPES)
            operation.add_argument("--effective-at")
    for operation in actions.choices.values():
        operation.add_argument("--project", required=True)


def run_review(args):
    action = args.review_action
    project = args.project.strip()
    if not project:
        raise ValueError("project must not be blank")
    if action == "propose":
        artifact = read_record(args.record, commit=args.commit, repo=args.repo,
                               recorded_at=args.recorded_at, quote=args.quote)
    elif not args.db.is_file():
        raise FileNotFoundError("review database does not exist; propose a candidate first")
    with SQLiteMemoryStore(args.db) as store:
        queue = ReviewQueue(store)
        if action == "propose":
            candidate, created = queue.propose(artifact=artifact, quote=args.quote, project_id=project,
                                               subject=args.subject, predicate=args.field, value=args.value,
                                               event_type=args.event_type, effective_at=args.effective_at)
            return {"created": created, "candidate": candidate.model_dump(mode="json")}
        if action == "list":
            return {"candidates": [row.model_dump(mode="json") for row in queue.list(project, args.status)]}
        if action == "show":
            candidate = queue.show(project, args.candidate_id)
        elif action == "edit":
            changes = {key: getattr(args, key) for key in ("value", "event_type", "effective_at")
                       if getattr(args, key) is not None}
            candidate = queue.edit(project, args.candidate_id, args.revision, **changes)
        else:
            decision = "confirmed" if action == "confirm" else "rejected"
            candidate = queue.decide(project, args.candidate_id, args.revision, decision=decision)
        return candidate.model_dump(mode="json")
