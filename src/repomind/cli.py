"""Offline import / structured query / reproducible evaluation commands."""

import argparse
import json
from pathlib import Path
import sqlite3
import sys

from repomind import __version__
from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import MemoryQuery
from repomind.memory.retriever import MemoryRetriever


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RepoMind V1 — offline structured project memory")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--db", type=Path, default=Path("repomind.sqlite3"), help="SQLite ledger path")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import", help="Atomically import structured JSONL events")
    importer.add_argument("path", type=Path)
    query = commands.add_parser("query", help="Query one exact project / subject / field at a time")
    query.add_argument("--project", required=True)
    query.add_argument("--subject", default="project")
    query.add_argument("--field", "--predicate", dest="predicate", required=True)
    query.add_argument("--as-of", required=True, help="UTC date (end of day) or ISO timestamp with zone")
    query.add_argument("--known-at", help="Optional observation cutoff; same date/time syntax")
    for command in (importer, query):
        command.add_argument("--db", type=Path, default=argparse.SUPPRESS, help="SQLite ledger path")
    evaluate = commands.add_parser("eval", help="Evaluate in a fresh temporary ledger; emit JSON and Markdown")
    evaluate.add_argument("--events", type=Path, default=Path("data/fixtures/conversations.jsonl"))
    evaluate.add_argument("--dataset", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True, help=".md or .json path; both formats are written")
    evaluate.add_argument("--baseline", action="store_true", help="Run latest-observation negative control")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "import":
            with SQLiteMemoryStore(args.db) as store:
                result = store.import_jsonl(args.path)
                output = {**result.model_dump(), "total_events": store.count(), "db": str(args.db)}
        elif args.command == "query":
            query = MemoryQuery(project_id=args.project, subject=args.subject, predicate=args.predicate,
                                as_of=args.as_of, known_at=args.known_at)
            if not args.db.is_file():
                raise FileNotFoundError(f"database does not exist: {args.db}; import events first")
            with SQLiteMemoryStore(args.db) as store:
                output = MemoryRetriever(store).query(query).model_dump(mode="json")
        else:
            from repomind.evaluation.runner import run_evaluation

            report = run_evaluation(args.events, args.dataset, args.output, baseline=args.baseline)
            output = {"metrics": report["metrics"], "markdown": str(args.output.with_suffix(".md")),
                      "json": str(args.output.with_suffix(".json"))}
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0 if report["metrics"]["correct"] == report["metrics"]["total"] else 1
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
