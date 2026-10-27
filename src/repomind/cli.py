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
    parser = argparse.ArgumentParser(description="RepoMind — temporal project memory and grounded intelligent retrieval")
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
    commands.add_parser("config", help="Show local configuration status without keys or network calls")
    ingest = commands.add_parser("ingest", help="Extract quoted memory candidates from natural-language JSONL sources")
    ingest.add_argument("path", type=Path)
    ingest.add_argument("--provider", choices=("live", "replay"), default="live")
    ingest.add_argument("--responses", type=Path, help="Recorded extraction responses; replay only")
    ingest.add_argument("--output", type=Path, required=True, help="Candidate JSONL; adjacent .audit.json preserves quotes")
    ingest.add_argument("--apply", action="store_true", help="Atomically persist sources, events and quotes")
    index = commands.add_parser("index", help="Build an explicitly configured project embedding snapshot")
    index.add_argument("--project", required=True)
    index.add_argument("--known-at")
    search = commands.add_parser("search", help="Find fact keys, then apply the complete temporal resolver")
    search.add_argument("--project", required=True)
    search.add_argument("--text", required=True)
    search.add_argument("--as-of", required=True)
    search.add_argument("--known-at")
    search.add_argument("--mode", choices=("lexical", "semantic", "hybrid"), default="hybrid")
    search.add_argument("--top-k", type=int, default=5)
    search.add_argument("--min-cosine", type=float, default=0.2)
    for command in (index, search):
        command.add_argument("--provider", choices=("live", "recorded"), default="live")
        command.add_argument("--vectors", type=Path, help="Recorded test vectors; recorded provider only")
    source = commands.add_parser("source", help="Inspect a persisted natural-language source and extraction provenance")
    source.add_argument("--project", required=True)
    source.add_argument("--source-id", required=True)
    for command in (ingest, index, search, source):
        command.add_argument("--db", type=Path, default=argparse.SUPPRESS)
    intelligent = commands.add_parser("eval-intelligence", help="Separate extraction, retrieval and end-to-end evaluation")
    intelligent.add_argument("--dataset", type=Path, required=True)
    intelligent.add_argument("--seeds", type=Path, default=Path("data/v1.1/seed-events.jsonl"))
    intelligent.add_argument("--gold-events", type=Path, default=Path("data/v1.1/gold-events.jsonl"))
    intelligent.add_argument("--responses", type=Path, default=Path("data/v1.1/extraction-responses.jsonl"))
    intelligent.add_argument("--vectors", type=Path)
    intelligent.add_argument("--provider", choices=("replay", "live"), default="replay")
    intelligent.add_argument("--search-mode", choices=("lexical", "semantic", "hybrid"), default="lexical")
    intelligent.add_argument("--output", type=Path, required=True)
    return parser


def _embedding_provider(args):
    if args.provider == "recorded":
        from repomind.intelligence.replay import RecordedEmbedder
        if args.vectors is None:
            raise ValueError("recorded embedding provider requires --vectors")
        return RecordedEmbedder(args.vectors)
    from repomind.intelligence.dashscope import embedding_provider_from_env
    return embedding_provider_from_env()


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
        elif args.command == "config":
            from repomind.intelligence.config import configuration_status
            output = configuration_status()
        elif args.command == "ingest":
            from repomind.intelligence.ingestion import prepare_ingestion, read_sources, write_candidate_bundle, validate_output_paths
            from repomind.intelligence.providers import OpenAICompatibleProvider, ProviderConfig, ReplayExtractionProvider
            if args.provider == "replay" and args.responses is None:
                raise ValueError("replay extraction provider requires --responses")
            validate_output_paths(args.output, [args.path, args.db] + ([args.responses] if args.responses else []))
            provider = (ReplayExtractionProvider(args.responses) if args.provider == "replay"
                        else OpenAICompatibleProvider(ProviderConfig.from_env()))
            sources = read_sources(args.path)
            with SQLiteMemoryStore(args.db if args.apply or args.db.is_file() else ":memory:") as store:
                memories = prepare_ingestion(store, sources, provider)
                artifacts = write_candidate_bundle(memories, args.output,
                    [args.path] + ([args.responses] if args.responses else []) + [args.db])
                imported = store.import_extractions(memories).model_dump() if args.apply else None
            output = {"provider": provider.name, "applied": args.apply, "import": imported, **artifacts,
                      "source_count": len(sources), "abstentions": sum(not m.events for m in memories)}
        elif args.command in ("index", "search"):
            from repomind.intelligence.search import HybridMemorySearch
            if not args.db.is_file():
                raise FileNotFoundError(f"database does not exist: {args.db}; import or ingest first")
            embedder = None if args.command == "search" and args.mode == "lexical" else _embedding_provider(args)
            with SQLiteMemoryStore(args.db) as store:
                retriever = HybridMemorySearch(store, embedder)
                if args.command == "index":
                    output = retriever.index(args.project, known_at=args.known_at)
                else:
                    output = retriever.search(args.project, args.text, args.as_of, known_at=args.known_at,
                        top_k=args.top_k, mode=args.mode, min_cosine=args.min_cosine)
        elif args.command == "source":
            if not args.db.is_file():
                raise FileNotFoundError(f"database does not exist: {args.db}")
            with SQLiteMemoryStore(args.db) as store:
                record = store.get_source(args.project, args.source_id)
                provenance = [store.get_provenance(event.event_id) for event in store.project_events(args.project)
                              if event.source_id == args.source_id]
                output = {"status": "ok" if record else "unknown", "source": record,
                          "provenance": [item for item in provenance if item is not None]}
        elif args.command == "eval-intelligence":
            from repomind.evaluation.intelligent import run_intelligent_evaluation
            report = run_intelligent_evaluation(args.seeds, args.gold_events, args.dataset, args.output,
                responses_path=args.responses, vectors_path=args.vectors, live=args.provider == "live",
                search_mode=args.search_mode)
            print(json.dumps({"metrics": report["metrics"], "validation": report["validation"],
                              "output": str(args.output)}, ensure_ascii=False, indent=2))
            return 0 if report["metrics"]["all_passed"] else 1
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
