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
    query.add_argument("--with-sources", action="store_true", help="Resolve citations to stored evidence and artifact locators")
    for command in (importer, query):
        command.add_argument("--db", type=Path, default=argparse.SUPPRESS, help="SQLite ledger path")
    from repomind.memory.review_cli import add_review_parser
    add_review_parser(commands)
    from repomind.codex_cli import add_codex_parser
    add_codex_parser(commands)
    from repomind.web.server import add_web_parser
    add_web_parser(commands)
    from repomind.memory_effect_cli import add_parser as add_effect_parser
    add_effect_parser(commands)
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
    search.add_argument("--min-cosine", type=float, help="Cosine cutoff; default from local profile or 0.2")
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
    intelligent.add_argument("--min-cosine", type=float, help="Explicit cosine cutoff; offline default 0.2")
    compare = commands.add_parser("compare", help="Compare controlled retrieval backends; never auto-export traces")
    compare.add_argument("--events", type=Path, default=Path("data/v1.2/events.jsonl"))
    compare.add_argument("--dataset", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True, help=".md or .json report; both formats are written")
    compare.add_argument("--vector-mode", choices=("recorded", "live"), default="recorded")
    compare.add_argument("--vectors", type=Path, help="Recorded mode defaults to data/v1.2/recorded-vectors.json")
    compare.add_argument("--variants", nargs="+", choices=("no_memory", "repomind_semantic", "repomind_hybrid", "mem0"))
    compare.add_argument("--run-id")
    compare.add_argument("--state-dir", type=Path, help="Parent directory; a fresh run_id child is required")
    compare.add_argument("--outbox", type=Path, help="Local trace outbox; cloud export requires trace-sync")
    compare.add_argument("--pricing", type=Path, help="Optional explicit versioned price card for estimates")
    compare.add_argument("--seed", type=int, default=0)
    compare.add_argument("--min-cosine", type=float, default=0.55, help="Shared strict cosine cutoff; top_k remains 3")
    sync = commands.add_parser("trace-sync", help="Explicitly export synthetic precomputed traces/experiments to Langfuse")
    sync.add_argument("sync_mode", nargs="?", choices=("traces", "experiment", "both"), default="traces")
    sync.add_argument("--outbox", type=Path, required=True)
    sync.add_argument("--dataset-name", default="repomind-comparison")
    sync.add_argument("--run-name")
    sync.add_argument("--verify-only", action="store_true", help="Read back existing objects only; never re-emit spans/datasets/scores")
    sync.add_argument("--receipt", type=Path, help="Optional safe delivery JSON; cannot overwrite outbox/status/config")
    prepare = commands.add_parser("agent-prepare", help="Explicitly build a trusted local Docker pytest image")
    prepare.add_argument("--output", type=Path, default=Path("work/v2-sandbox.json"))
    prepare.add_argument("--config-dir", type=Path, default=Path("work/v2-docker-config"))
    prepare.add_argument("--project-root", type=Path, default=Path.cwd(), help="RepoMind source root containing docker/v2")
    doctor = commands.add_parser("agent-doctor", help="Verify the local isolated code-test image; no model call")
    doctor.add_argument("--image")
    doctor.add_argument("--sandbox-config", type=Path, default=Path("work/v2-sandbox.json"))
    doctor.add_argument("--config-dir", type=Path, default=Path("work/v2-docker-config"))
    agent = commands.add_parser("agent-bench", help="Run frozen code tasks with bounded tools and isolated grading")
    agent.add_argument("--dataset", type=Path, required=True)
    agent.add_argument("--data-root", type=Path, default=Path("data/v2"))
    agent.add_argument("--output", type=Path, required=True)
    agent.add_argument("--provider", choices=("live", "replay"), default="replay")
    agent.add_argument("--variants", nargs="+", choices=("baseline", "memory", "enhanced"))
    agent.add_argument("--image")
    agent.add_argument("--sandbox-config", type=Path, default=Path("work/v2-sandbox.json"))
    agent.add_argument("--config-dir", type=Path, default=Path("work/v2-docker-config"))
    agent.add_argument("--state-dir", type=Path, default=Path("work/v2-runs"))
    agent.add_argument("--run-id")
    agent.add_argument("--seed", type=int, default=0)
    agent.add_argument("--max-turns", type=int, default=6)
    agent.add_argument("--max-test-runs", type=int, default=3)
    agent.add_argument("--pricing", type=Path)
    from repomind.context.selection import STRATEGIES
    context = commands.add_parser("context-select", help="Select project evidence under an explicit byte budget")
    context.add_argument("--corpus", type=Path, default=Path("data/v2.1/corpus.json"))
    context.add_argument("--project", required=True)
    context.add_argument("--query", required=True)
    context.add_argument("--strategy", choices=STRATEGIES, default="layered")
    context.add_argument("--budget", type=int, default=1536, help="Maximum UTF-8 bytes of evidence JSON")
    context.add_argument("--openviking-root", help="Read layered data from a named viking://resources subtree")
    bench = commands.add_parser("context-bench", help="Compare direct, vector, and layered context on frozen questions")
    bench.add_argument("--data-root", type=Path, default=Path("data/v2.1"))
    bench.add_argument("--split", choices=("dev", "holdout"), default="dev")
    bench.add_argument("--budgets", nargs="+", type=int, default=(640, 1800))
    bench.add_argument("--live", action="store_true", help="Use configured embedding and chat services")
    bench.add_argument("--output", type=Path, required=True)
    for phase in ("tune", "validate"):
        harness = commands.add_parser("harness-" + phase, help="Run the " + phase + " phase of a bounded harness experiment")
        harness.add_argument("--suite", type=Path, default=Path("data/v3"))
        harness.add_argument("--history", type=Path, default=Path("reports/v2/live-dev-r2.traces.jsonl"))
        harness.add_argument("--run-dir", type=Path, required=True)
        harness.add_argument("--live", action="store_true", help="Use the configured real chat model")
        harness.add_argument("--image")
        harness.add_argument("--sandbox-config", type=Path, default=Path("work/v2-sandbox.json"))
        harness.add_argument("--config-dir", type=Path, default=Path("work/v2-docker-config"))
    return parser


def _agent_image(args):
    if args.image:
        return args.image
    if not args.sandbox_config.is_file():
        raise ValueError("agent sandbox config missing; run agent-prepare explicitly first")
    config=json.loads(args.sandbox_config.read_text(encoding="utf-8"))
    if not isinstance(config,dict) or not isinstance(config.get("image"),str):
        raise ValueError("sandbox config must contain an immutable image ID")
    return config["image"]


def _embedding_provider(args):
    if args.provider == "recorded":
        from repomind.intelligence.replay import RecordedEmbedder
        if args.vectors is None:
            raise ValueError("recorded embedding provider requires --vectors")
        return RecordedEmbedder(args.vectors)
    from repomind.intelligence.dashscope import embedding_provider_from_env
    return embedding_provider_from_env()


def _trace_sync(args) -> dict:
    if not args.outbox.is_file():
        raise FileNotFoundError(f"trace outbox does not exist: {args.outbox}")
    if args.receipt is not None:
        protected = {args.outbox.resolve(), Path(str(args.outbox) + ".status.jsonl").resolve()}
        name = args.receipt.name.lower()
        if args.receipt.resolve() in protected or name == ".env" or name.startswith(".env."):
            raise ValueError("delivery receipt must not overwrite outbox, status journal, or configuration files")
    from repomind.intelligence.config import load_env_file
    from repomind.platform.langfuse import LangfuseConfig, LangfuseExporter
    from repomind.platform.tracing import TraceOutbox, clean_payload

    outbox = TraceOutbox(args.outbox)
    # Validate local input before loading credentials or constructing an exporter.
    records=outbox.records()
    load_env_file()
    settings = LangfuseConfig.from_env()
    exporter = LangfuseExporter(settings)
    export_stage="V2.0" if any(record.stage=="developer_task" for record in records) else "V1.2"
    receipt = {"stage_goal": export_stage+" explicit Langfuse export with service read-back confirmation",
               "mode": args.sync_mode, "outbox": str(args.outbox), "model_executed_during_export": False,
               "verify_only": args.verify_only}
    try:
        if args.sync_mode in {"traces", "both"}:
            receipt["traces"] = exporter.sync(outbox, **({"verify_only": True} if args.verify_only else {}))
        if args.sync_mode in {"experiment", "both"}:
            receipt["experiment"] = exporter.export_experiment(outbox, args.dataset_name, run_name=args.run_name,
                **({"verify_only": True} if args.verify_only else {}))
    except Exception:
        raise ValueError("Langfuse sync failed; sensitive upstream details omitted; inspect the local status journal") from None
    finally:
        close = getattr(exporter, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                raise ValueError("Langfuse exporter shutdown failed; sensitive upstream details omitted") from None
    requested = [receipt[key] for key in ("traces", "experiment") if key in receipt]
    receipt["cloud_verified"] = bool(requested) and all(result.get("cloud_verified") is True for result in requested)
    receipt = clean_payload(receipt)
    if args.receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "memory-compare":
            from repomind.memory_effect_cli import run
            output=run(args)
            print(json.dumps(output,ensure_ascii=False,indent=2))
            return 0 if output.get('status','completed')!='failed' else 1
        elif args.command == "web":
            from repomind.web.server import run_web

            return run_web(args)
        elif args.command == "import":
            with SQLiteMemoryStore(args.db) as store:
                result = store.import_jsonl(args.path)
                output = {**result.model_dump(), "total_events": store.count(), "db": str(args.db)}
        elif args.command == "review":
            from repomind.memory.review_cli import run_review

            output = run_review(args)
        elif args.command == "codex":
            from repomind.codex_cli import run_codex

            output = run_codex(args)
        elif args.command == "query":
            query = MemoryQuery(project_id=args.project, subject=args.subject, predicate=args.predicate,
                                as_of=args.as_of, known_at=args.known_at)
            if not args.db.is_file():
                raise FileNotFoundError(f"database does not exist: {args.db}; import events first")
            with SQLiteMemoryStore(args.db) as store:
                output = MemoryRetriever(store).query(query).model_dump(mode="json")
                if args.with_sources:
                    from repomind.memory.review import review_artifact

                    output["sources"] = [
                        {"source_id": event["source_id"], "event_id": event["event_id"],
                         "record": store.get_source(query.project_id, event["source_id"]),
                         "provenance": store.get_provenance(event["event_id"]),
                         "artifact": review_artifact(store, query.project_id, event["source_id"])}
                        for event in output["evidence"]
                    ]
        elif args.command == "config":
            from repomind.intelligence.config import configuration_status
            output = configuration_status()
        elif args.command in ("harness-tune", "harness-validate"):
            from repomind.harness.experiment import run_phase

            phase = args.command.removeprefix("harness-")
            report = run_phase(phase, suite=args.suite, history=args.history, run_dir=args.run_dir,
                               image=_agent_image(args), config_dir=args.config_dir, live=args.live)
            keys = ("split", "metrics", "locked_challenger", "holdout_gate", "promotion_supported", "recommended_policy")
            print(json.dumps({key: report[key] for key in keys if key in report}, ensure_ascii=False, indent=2))
            return int(not report["completed_without_infrastructure_errors"])
        elif args.command == "context-select":
            import os
            from repomind.context.selection import Corpus, ContextSelector
            from repomind.context.openviking import OpenVikingReader
            from repomind.intelligence.config import load_env_file
            from repomind.intelligence.dashscope import embedding_provider_from_env

            reader = None
            if args.openviking_root:
                if args.strategy != "layered":
                    raise ValueError("OpenViking requires --strategy layered")
                load_env_file()
                reader = OpenVikingReader(os.environ.get("REPOMIND_OPENVIKING_URL", "http://127.0.0.1:1933"),
                                         args.openviking_root, os.environ.get("REPOMIND_OPENVIKING_KEY") or None)
            embedder = embedding_provider_from_env() if args.strategy == "vector" else None
            selector = ContextSelector(Corpus.load(args.corpus), embedder=embedder, reader=reader)
            if embedder is not None:
                selector.index(args.project)
            output = selector.select(args.project, args.query, args.strategy, args.budget)
        elif args.command == "context-bench":
            from repomind.context.benchmark import LiveAnswerer, run_benchmark
            from repomind.intelligence.dashscope import embedding_provider_from_env

            path = args.output.resolve()
            if path.suffix != ".json" or path.is_relative_to(args.data_root.resolve()) or path.exists():
                raise ValueError("context benchmark requires a new .json output outside frozen data")
            path.parent.mkdir(parents=True, exist_ok=True)
            report = run_benchmark(args.data_root, args.split, tuple(args.budgets),
                                   embedder=embedding_provider_from_env() if args.live else None,
                                   answerer=LiveAnswerer() if args.live else None)
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
            print(json.dumps({"output": str(path), "summary": report["summary"]}, ensure_ascii=False, indent=2))
            return int(any(row["model_errors"] for row in report["summary"]))
        elif args.command == "agent-prepare":
            from repomind.agent.sandbox import prepare_image
            if args.output.suffix != ".json" or args.output.name.startswith(".env"):
                raise ValueError("sandbox configuration output must be a .json file")
            output = prepare_image(args.project_root,args.config_dir,output_path=args.output)
        elif args.command == "agent-doctor":
            from repomind.agent.sandbox import DockerSandbox
            output = DockerSandbox(_agent_image(args),args.config_dir).probe()
        elif args.command == "agent-bench":
            from repomind.agent.benchmark import run_developer_benchmark
            from repomind.agent.models import AgentBudget
            report=run_developer_benchmark(args.dataset,args.output,image=_agent_image(args),config_dir=args.config_dir,
                data_root=args.data_root,provider_mode=args.provider,variants=args.variants,state_dir=args.state_dir,
                run_id=args.run_id,seed=args.seed,budget=AgentBudget(max_turns=args.max_turns,max_test_runs=args.max_test_runs),
                pricing_path=args.pricing)
            print(json.dumps({"validation":report["validation"],"variants":{name:arm["metrics"] for name,arm in report["variants"].items()},
                              "outbox":report["outbox"],"output":str(args.output)},ensure_ascii=False,indent=2))
            return 0 if report["validation"]["completed_without_errors"] else 1
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
            from repomind.intelligence.config import search_min_cosine
            if not args.db.is_file():
                raise FileNotFoundError(f"database does not exist: {args.db}; import or ingest first")
            embedder = None if args.command == "search" and args.mode == "lexical" else _embedding_provider(args)
            with SQLiteMemoryStore(args.db) as store:
                retriever = HybridMemorySearch(store, embedder)
                if args.command == "index":
                    output = retriever.index(args.project, known_at=args.known_at)
                else:
                    output = retriever.search(args.project, args.text, args.as_of, known_at=args.known_at,
                        top_k=args.top_k, mode=args.mode, min_cosine=search_min_cosine(args.min_cosine))
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
            from repomind.intelligence.config import search_min_cosine
            report = run_intelligent_evaluation(args.seeds, args.gold_events, args.dataset, args.output,
                responses_path=args.responses, vectors_path=args.vectors, live=args.provider == "live",
                search_mode=args.search_mode,
                min_cosine=search_min_cosine(args.min_cosine, read_file=args.provider == "live"))
            print(json.dumps({"metrics": report["metrics"], "validation": report["validation"],
                              "output": str(args.output)}, ensure_ascii=False, indent=2))
            return 0 if report["metrics"]["all_passed"] else 1
        elif args.command == "compare":
            if args.variants is not None and len(args.variants) != len(set(args.variants)):
                raise ValueError("comparison variants must not be repeated")
            if args.vector_mode == "live" and args.vectors is not None:
                raise ValueError("live comparison must not use recorded --vectors")
            from repomind.comparison.runner import run_comparison
            vectors = args.vectors
            if args.vector_mode == "recorded" and vectors is None:
                vectors = Path("data/v1.2/recorded-vectors.json")
            report = run_comparison(args.events, args.dataset, args.output,
                vector_mode=args.vector_mode, vectors_path=vectors, variants=args.variants,
                run_id=args.run_id, state_dir=args.state_dir, outbox_path=args.outbox,
                pricing_path=args.pricing, seed=args.seed, min_cosine=args.min_cosine)
            variants = {name: value.get("metrics", value) for name, value in report["variants"].items()}
            print(json.dumps({"validation": report["validation"], "variants": variants,
                              "outbox": report.get("outbox"), "markdown": str(args.output.with_suffix(".md")),
                              "json": str(args.output.with_suffix(".json"))}, ensure_ascii=False, indent=2))
            return 0 if report["validation"].get("completed_without_errors") is True else 1
        elif args.command == "trace-sync":
            output = _trace_sync(args)
            print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
            return 0 if output["cloud_verified"] is True else 1
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
