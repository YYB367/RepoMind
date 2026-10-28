"""Frozen-data, isolated-provider comparison; gold labels are scorer-only."""

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import random
import re
from time import perf_counter
from uuid import uuid4

from repomind import __version__
from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.comparison.base import ScopeViolationError
from repomind.comparison.pricing import estimate_cost, load_price_card
from repomind.comparison.providers import NativeMemoryProvider, NoMemoryProvider
from repomind.comparison.telemetry import MeasuredEmbedder
from repomind.domain.models import Text
from repomind.evaluation.intelligent import IntelligentQuery, _implementation_hash, _query_metrics, score_search_response
from repomind.memory.store import _unique_keys
from repomind.platform.tracing import TraceOutbox, TraceRecord, clean_payload

STAGE_GOAL = "V1.2：建立可复现的检索对照、实际用量计量和可读回核验的 Langfuse 追踪/实验"
VARIANTS = ("no_memory", "repomind_semantic", "repomind_hybrid", "mem0")


class ComparisonQuestion(IntelligentQuery):
    question_id: Text
    category: Text


def load_questions(path):
    questions, seen = [], set()
    for number, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            question = ComparisonQuestion.model_validate(json.loads(line, object_pairs_hook=_unique_keys))
            if question.question_id in seen:
                raise ValueError("duplicate question_id")
        except ValueError as exc:
            raise ValueError(f"invalid comparison question on line {number}") from exc
        questions.append(question)
        seen.add(question.question_id)
    if not questions:
        raise ValueError("comparison dataset must contain questions")
    return questions


def _file(path):
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _synthetic_manifest(events, dataset, vectors):
    path = events.parent / "manifest.json"
    if not path.is_file():
        return False, None
    manifest = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_keys)
    declared = manifest.get("synthetic") is True
    for selected in (events, dataset, vectors):
        if selected is None:
            continue
        try:
            relative = selected.resolve().relative_to(path.parent.resolve()).as_posix()
        except ValueError:
            return False, _file(path)
        expected = manifest.get("files", {}).get(relative, {}).get("sha256")
        if expected != _file(selected)["sha256"]:
            raise ValueError("selected benchmark input differs from its frozen manifest")
    return declared, _file(path)


def _percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _timing(values):
    return {"n": len(values), "total_seconds": sum(values),
            "p50_seconds": _percentile(values, .5), "p95_seconds": _percentile(values, .95),
            "percentile_method": "nearest-rank; small-sample descriptive only"}


def _metrics(scores):
    return {**_query_metrics(scores), "answer_correct_count": sum(score["answer_correct"] for score in scores),
            "source_set_correct_count": sum(score["sources_correct"] for score in scores),
            "failure_stage_counts": {stage: sum(score["failure_stage"] == stage for score in scores)
                                     for stage in ("retrieval", "resolution", "provenance")}}


def _make_embedder(vector_mode, vectors):
    if vector_mode == "recorded":
        from repomind.intelligence.replay import RecordedEmbedder
        provider = RecordedEmbedder(vectors)
    else:
        from repomind.intelligence.dashscope import embedding_provider_from_env
        provider = embedding_provider_from_env()
    return MeasuredEmbedder(provider, live=vector_mode == "live")


def _make_provider(name, store, embedder, directory, run_id):
    if name == "no_memory":
        return NoMemoryProvider()
    if name == "mem0":
        from repomind.comparison.mem0 import Mem0MemoryProvider
        return Mem0MemoryProvider(store, embedder, directory / "mem0", run_id)
    return NativeMemoryProvider(store, embedder, mode=name.removeprefix("repomind_"))


def _model(embedder):
    if embedder is None:
        return None
    return getattr(embedder.config, "embedding_model", None) or embedder.name


def _observations(calls, timings, model, card, live, run_date):
    observations = [{"name": name, "elapsed_seconds": seconds} for name, seconds in timings.items()]
    for call in calls:
        pricing = estimate_cost(call["usage_delta"], model, card, live=live, run_date=run_date,
                                usage_complete=call.get("usage_complete", False))
        observation = {"name": "embedding_" + call["operation"], "as_type": "generation" if live else "span",
            "model": model if live else None, "elapsed_seconds": call["elapsed_seconds"],
            "input": {"sha256": call["input_hashes"]}, "output": {"vector_sha256": call["vector_hashes"]},
            "usage_details": call["usage_delta"] if call.get("usage_complete") else None,
            "metadata": {"operation": call["operation"], "remote_request_delta": call["remote_request_delta"],
                         "error_type": call["error_type"], "pricing_result": pricing,
                         "usage_complete": call.get("usage_complete", False),
                         "observed_usage_delta": call["usage_delta"],
                         "original_started_at": call.get("started_at"), "original_ended_at": call.get("ended_at")}}
        if pricing["amount"] is not None and pricing["currency"] == "USD":
            observation["cost_details"] = {"total": pricing["amount"]}
        observations.append(observation)
    return observations


def _parity(variants):
    arms = {}
    for name, variant in variants.items():
        embedding = variant["metadata"].get("embedding")
        if embedding is None:
            continue
        inputs, outputs = defaultdict(set), defaultdict(set)
        for call in embedding.get("measured_calls", []):
            for position, input_hash in enumerate(call["input_hashes"]):
                key = call["operation"] + ":" + input_hash
                inputs[call["operation"]].add(input_hash)
                if call["vector_hashes"] is not None:
                    outputs[key].add(call["vector_hashes"][position])
        arms[name] = {"input_sets": {key: sorted(value) for key, value in inputs.items()},
                      "vector_digests_by_operation_and_input": {key: sorted(value) for key, value in outputs.items()}}
    input_sets = [value["input_sets"] for value in arms.values()]
    vector_sets = [value["vector_digests_by_operation_and_input"] for value in arms.values()]
    return {"arms": arms, "input_set_parity": all(value == input_sets[0] for value in input_sets) if input_sets else None,
            "vector_digest_parity": all(value == vector_sets[0] for value in vector_sets) if vector_sets else None,
            "claim": "Each arm independently calls the same configured embedder. Input sets exclude batching/cache multiplicity; numerical vectors may vary. No shared paid-call cache."}


def _render(report):
    lines = ["# 阶段目标：" + STAGE_GOAL, "", f"运行 `{report['run_id']}`；模式 `{report['config']['vector_mode']}`。", "",
             "受控检索比较：相同事实键文档/模型/项目和时间范围，共用 V1 resolver；Mem0 infer=False。", "",
             "| 方案 | 严格正确 | Recall@3 | 引用合法 | 越界查询 | 实际 API 请求 | 费用估算 |",
             "|---|---:|---:|---:|---:|---:|---|"]
    for name, variant in report["variants"].items():
        metrics = variant["metrics"]
        percent = lambda value: "N/A" if value is None else f"{value:.1%}"
        embedding = variant["metadata"].get("embedding") or {}
        pricing = variant["pricing"]
        cost = "未知（" + pricing["status"] + "）" if pricing["amount"] is None else str(pricing["amount"]) + " " + pricing["currency"] + "（估算）"
        lines.append(f"| {name} | {metrics['correct']}/{metrics['total_queries']} | {percent(metrics['recall_at_3'])} | {percent(metrics['source_validity'])} | {metrics['project_leakage_count']} | {embedding.get('request_count', 0)} | {cost} |")
    lines += ["", "## 计量与结论边界", "", "- search_and_resolution 包含检索和 V1 规则解析；不声称单独测得 resolver 耗时。索引、查询、评分、准备和报告写入分别计时。",
              "- 延迟是单轮小样本描述，含 Mem0 本地 HTTP 桥开销。原始索引/热缓存次数见 JSON；不能外推吞吐量或生产可靠性。",
              "- 无记忆组是负对照；工程完成标志不以它的准确率为门槛。各组实际失败案例全部保留。",
              "- recorded 是理想排序测试替身，不能证明真实语义质量或节省费用；live 的 token 来自真实返回，费用只有显式价卡估算，不等于账单。",
              "- 纯语义自研与 Mem0 是主要受控对照；混合检索额外使用词法信号。共享 resolver 意味着本结果不评测 Mem0 原生事实提取/冲突/时间处理。",
              "- 本地 outbox 成功不等于云端保存；trace-sync 后仍需云端读回证据。Experiment 回放预计算输出，不重调模型。", "",
              "## 运行配置", "", "```json", json.dumps(report["config"], ensure_ascii=False, indent=2), "```", "",
              "## 延迟与分类指标", "", "```json", json.dumps({name: {"timings": value["timings"], "by_category": value["by_category"]} for name, value in report["variants"].items()}, ensure_ascii=False, indent=2), "```", "",
              "## 失败案例", "", "```json", json.dumps(report["failures"], ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines)


def run_comparison(events_path, dataset_path, output_path, *, vector_mode="recorded", vectors_path=None,
                   variants=None, run_id=None, state_dir=None, outbox_path=None, pricing_path=None,
                   seed=0, min_cosine=.55):
    started = perf_counter()
    events, dataset, output = map(Path, (events_path, dataset_path, output_path))
    vectors = Path(vectors_path) if vectors_path is not None else None
    if vector_mode not in {"recorded", "live"} or (vector_mode == "recorded" and vectors is None):
        raise ValueError("recorded comparison requires vectors_path; vector_mode must be recorded or live")
    if vector_mode == "live" and vectors is not None:
        raise ValueError("live comparison must not use recorded vectors")
    if output.suffix.lower() not in {".md", ".json"}:
        raise ValueError("comparison output must end in .md or .json")
    if type(seed) is not int or type(min_cosine) not in (int, float) or not math.isfinite(min_cosine) or not 0 <= min_cosine < 1:
        raise ValueError("seed must be int and min_cosine must be finite in [0, 1)")
    names = list(VARIANTS if variants is None else variants)
    if not names or len(set(names)) != len(names) or any(name not in VARIANTS for name in names):
        raise ValueError("variants must contain unique supported provider names")
    run_id = run_id or ("v12-" + uuid4().hex)
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id):
        raise ValueError("run_id must be 1..80 ASCII filename-safe characters")
    run_directory = (Path(state_dir) if state_dir is not None else Path("work/comparisons")) / run_id
    outbox_path = Path(outbox_path) if outbox_path is not None else output.with_suffix(".traces.jsonl")
    targets = [output.with_suffix(".json"), output.with_suffix(".md"), outbox_path,
               Path(str(outbox_path) + ".status.jsonl")]
    inputs = [events, dataset] + ([vectors] if vectors else []) + ([Path(pricing_path)] if pricing_path else [])
    if len({path.resolve() for path in targets}) != len(targets):
        raise ValueError("comparison output paths must be distinct")
    runtime_arms = [run_directory.resolve() / name for name in names]
    if any(path.resolve().is_relative_to(arm) for path in targets for arm in runtime_arms):
        raise ValueError("comparison reports/outbox must not overlap provider runtime directories")
    if {path.resolve() for path in targets} & {path.resolve() for path in inputs}:
        raise ValueError("comparison must not overwrite its input files")
    if any(path.exists() for path in targets) or run_directory.exists():
        raise ValueError("comparison output/run already exists; preserve evidence and use fresh paths/run_id")
    questions = load_questions(dataset)
    synthetic, manifest = _synthetic_manifest(events, dataset, vectors)
    card, card_hash = load_price_card(pricing_path) if pricing_path is not None else (None, None)
    # Validate events before creating any provider or making any paid requests.
    with SQLiteMemoryStore(":memory:") as validation_store:
        validation_store.import_jsonl(events)
        event_count = validation_store.count()
    run_directory.mkdir(parents=True, exist_ok=False)
    order = list(names)
    random.Random(seed).shuffle(order)
    outbox = TraceOutbox(outbox_path)
    run_date = datetime.now(timezone.utc).date()
    results, failures = {}, []
    preparation_seconds = perf_counter() - started
    for name in order:
        directory = run_directory / name
        directory.mkdir()
        provider, embedder, setup_error = None, None, None
        setup_started = perf_counter()
        with SQLiteMemoryStore(directory / "ledger.sqlite3") as store:
            store.import_jsonl(events)
            try:
                embedder = None if name == "no_memory" else _make_embedder(vector_mode, vectors)
                provider = _make_provider(name, store, embedder, directory, run_id)
            except Exception as exc:
                setup_error = type(exc).__name__
            setup_seconds = perf_counter() - setup_started
            rows = []
            try:
                for question in questions:
                    call_start = len(embedder.calls) if embedder else 0
                    timings, response, index_result, error = {}, {}, {}, setup_error
                    phase = "setup" if setup_error else "index"
                    try:
                        if error is None:
                            clock = perf_counter()
                            try:
                                index_result = provider.index(question.project_id, known_at=question.known_at)
                            finally:
                                timings["index"] = perf_counter() - clock
                            phase, clock = "search_and_resolution", perf_counter()
                            try:
                                response = provider.search(question.project_id, question.text, question.as_of,
                                    known_at=question.known_at, top_k=3, min_cosine=min_cosine)
                            finally:
                                timings["search_and_resolution"] = perf_counter() - clock
                    except Exception as exc:
                        error = type(exc).__name__
                    clock = perf_counter()
                    score = score_search_response(question, response, store, error=error)
                    timings["scoring"] = perf_counter() - clock
                    if error == ScopeViolationError.__name__:
                        score["project_leakage"] = True
                    calls = embedder.calls[call_start:] if embedder else []
                    row = {"question_id": question.question_id, "category": question.category,
                           "index": index_result, "response": response, "score": score, "timings": timings,
                           "error_phase": phase if error else None, "embedding_call_count": len(calls)}
                    rows.append(row)
                    if not score["passed"]:
                        failures.append({"provider": name, "question_id": question.question_id,
                                         "error_phase": row["error_phase"], "details": score})
                    numeric_scores = {"strict_correct": float(score["passed"]), "answer_correct": float(score["answer_correct"]),
                                      "project_leakage": float(score["project_leakage"])}
                    if question.expected_key is not None:
                        numeric_scores["recall_at_3"] = float(score["recalled_at_3"])
                    if score["citation_total"]:
                        numeric_scores["source_validity"] = score["citation_valid"] / score["citation_total"]
                    outbox.append(TraceRecord(run_id=run_id, item_id=question.question_id, provider=name,
                        project_id=question.project_id, stage="query", synthetic=synthetic,
                        input=question.model_dump(mode="json", exclude={"expected_key", "expected_status", "expected_value", "expected_source_ids"}),
                        expected_output=question.model_dump(mode="json", include={"expected_key", "expected_status", "expected_value", "expected_source_ids"}),
                        output={"response": response, "actual_status": score["actual_status"], "actual_value": score["actual_value"],
                                "actual_source_ids": score["actual_source_ids"], "error_type": error}, scores=numeric_scores,
                        observations=_observations(calls, timings, _model(embedder), card, vector_mode == "live", run_date),
                        metadata={"vector_mode": vector_mode, "category": question.category, "timings": timings,
                                  "error_phase": row["error_phase"], "comparison_scope": "controlled retrieval; shared resolver; Mem0 infer=False",
                                  "model_work_performed_on_export": False}))
                metadata = provider.safe_metadata() if provider else {"name": name, "setup_error": setup_error, "embedding": embedder.safe_metadata() if embedder else None}
                scores = [row["score"] for row in rows]
                metrics = _metrics(scores)
                metrics["infrastructure_error_count"] = sum(score["error"] is not None for score in scores)
                timing_summary = {phase: _timing([row["timings"][phase] for row in rows if phase in row["timings"]])
                                  for phase in ("index", "search_and_resolution", "scoring")}
                timing_summary["setup_seconds"] = setup_seconds
                timing_summary["cold_index_requests"] = sum(row["index"].get("requested", 0) > 0 for row in rows)
                timing_summary["warm_index_requests"] = sum(row["index"].get("cached", 0) > 0 and row["index"].get("requested", 0) == 0 for row in rows)
                results[name] = {"metrics": metrics, "metadata": metadata, "timings": timing_summary,
                    "pricing": estimate_cost(embedder.usage if embedder else {}, _model(embedder), card,
                        live=vector_mode == "live", run_date=run_date,
                        usage_complete=embedder.usage_complete if embedder else False),
                    "by_category": {category: _metrics([row["score"] for row in rows if row["category"] == category])
                                    for category in sorted({row["category"] for row in rows})}, "queries": rows}
            finally:
                cleanup_errors = []
                if provider is not None:
                    try:
                        provider.close()
                    except Exception as exc:
                        cleanup_errors.append({"component": "memory_provider", "error_type": type(exc).__name__})
                closer = getattr(getattr(embedder, "provider", None), "close", None)
                if callable(closer):
                    try:
                        closer()
                    except Exception as exc:
                        cleanup_errors.append({"component": "embedder", "error_type": type(exc).__name__})
            results[name]["cleanup_errors"] = cleanup_errors
    try:
        versions = {name: importlib.metadata.version(name) for name in ("pydantic",)}
        for dependency in ("langfuse", "mem0ai", "qdrant-client", "openai"):
            try:
                versions[dependency] = importlib.metadata.version(dependency)
            except importlib.metadata.PackageNotFoundError:
                versions[dependency] = "not-installed"
    except importlib.metadata.PackageNotFoundError:
        versions = {}
    report = {"stage_goal": STAGE_GOAL, "run_id": run_id, "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {"version": __version__, "python": platform.python_version(), "sdk_versions": versions,
            "implementation_sha256": _implementation_hash(), "vector_mode": vector_mode,
            "events": _file(events), "dataset": _file(dataset), "vectors": _file(vectors) if vectors else None,
            "manifest": manifest, "synthetic": synthetic, "event_count": event_count, "query_count": len(questions),
            "top_k": 3, "min_cosine": min_cosine, "seed": seed, "provider_order": order,
            "state_directory": str(run_directory.resolve()), "price_card_sha256": card_hash,
            "same_data_policy": "independent store + embedding client per arm; no gold passed to provider; no shared paid-call cache",
            "primary_comparison": ["repomind_semantic", "mem0"], "resolver_timing": "included in search_and_resolution"},
        "variants": results, "vector_parity": _parity(results), "failures": failures,
        "timings": {"preparation_seconds": preparation_seconds, "comparison_seconds_before_report": perf_counter() - started,
                    "report_serialization_and_write_seconds": None},
        "outbox": str(outbox_path.resolve()), "validation": {
            "completed_without_errors": all(value["metrics"]["infrastructure_error_count"] == 0 and value["metrics"]["project_leakage_count"] == 0 and not value["cleanup_errors"] for value in results.values()),
            "cloud_verified": False, "quality_claim": "small synthetic live sample" if vector_mode == "live" else "ideal-ranking contract replay only",
            "baseline_accuracy_is_not_engineering_gate": True}}
    report = clean_payload(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    clock = perf_counter()
    # Store a measured first serialization/write pass, then finalize that field.
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    output.with_suffix(".md").write_text(_render(report), encoding="utf-8", newline="\n")
    report["timings"]["report_serialization_and_write_seconds"] = perf_counter() - clock
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    return report
