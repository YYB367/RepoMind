"""V1.1 extraction, gold retrieval, and end-to-end evaluation.

Recorded responses/vectors establish engineering behavior, never model quality.
Gold labels are used only by scorers, not supplied to extraction or retrieval.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sqlite3
import tempfile
from time import perf_counter
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator, model_validator

from repomind import __version__
from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import Contract, Event, MemoryQuery, QueryResult, Text, parse_timestamp
from repomind.intelligence.extraction import Extractor
from repomind.intelligence.models import CandidateFact, ExtractedMemory, SourceMessage
from repomind.intelligence.providers import OpenAICompatibleProvider, ProviderConfig, ReplayExtractionProvider
from repomind.intelligence.replay import RecordedEmbedder
from repomind.intelligence.search import HybridMemorySearch
from repomind.memory.store import _unique_keys

STAGE_GOAL = "V1.1：分别验证有来源的事实提取、人工事件检索和端到端记忆回答"
RELEASE_THRESHOLDS = {
    "extraction_precision_min": 0.90,
    "extraction_recall_min": 0.85,
    "gold_retrieval_recall_at_3_min": 0.90,
    "end_to_end_accuracy_min": 0.80,
    "source_validity_required": 1.0,
    "project_leakage_max": 0,
}


class GoldFact(CandidateFact):
    @model_validator(mode="after")
    def explicit_gold_time(self) -> "GoldFact":
        if self.effective_at is None:
            raise ValueError("gold expected_facts require explicit effective_at")
        return self


class IntelligentQuery(Contract):
    project_id: Text
    text: Text
    as_of: datetime
    known_at: datetime | None = None
    expected_key: tuple[Text, Text] | None
    expected_status: Literal["ok", "unknown", "insufficient_evidence"]
    expected_value: Text | None
    expected_source_ids: list[Text]

    @field_validator("as_of", "known_at", mode="before")
    @classmethod
    def explicit_query_time(cls, value: object) -> datetime | None:
        return None if value is None else parse_timestamp(value, allow_date=True)

    @model_validator(mode="after")
    def consistent_gold_answer(self) -> "IntelligentQuery":
        if len(self.expected_source_ids) != len(set(self.expected_source_ids)):
            raise ValueError("expected_source_ids must be unique")
        if self.expected_status == "ok" and (self.expected_value is None or not self.expected_source_ids):
            raise ValueError("ok requires expected_value and expected_source_ids")
        if self.expected_status != "ok" and self.expected_value is not None:
            raise ValueError("refusal must have expected_value=null")
        if self.expected_status == "unknown" and self.expected_source_ids:
            raise ValueError("unknown cannot cite expected fact sources")
        if self.expected_key is None and self.expected_status != "unknown":
            raise ValueError("a query with no expected key must expect unknown")
        return self


class IntelligentCase(Contract):
    case_id: Text
    source: SourceMessage
    expected_facts: list[GoldFact]
    queries: Annotated[list[IntelligentQuery], Field(min_length=1)]

    @model_validator(mode="after")
    def gold_quotes_exist(self) -> "IntelligentCase":
        if any(fact.evidence_text not in self.source.text for fact in self.expected_facts):
            raise ValueError("gold evidence_text must occur in the case source")
        if any(fact.event_type != "plan" and fact.effective_at > self.source.observed_at for fact in self.expected_facts):
            raise ValueError("gold implemented facts cannot take effect after source observation")
        return self


def load_intelligent_cases(path: str | Path) -> list[IntelligentCase]:
    path = Path(path)
    cases: list[IntelligentCase] = []
    seen: set[str] = set()
    sources: dict[tuple[str, str], str] = {}
    with path.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                case = IntelligentCase.model_validate(json.loads(line, object_pairs_hook=_unique_keys))
                if case.case_id in seen:
                    raise ValueError("duplicate case_id")
                source_key = case.source.project_id, case.source.source_id
                if source_key in sources and sources[source_key] != case.source.content_hash:
                    raise ValueError("source_id reused with different source content")
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
            seen.add(case.case_id)
            sources[source_key] = case.source.content_hash
            cases.append(case)
    if not cases:
        raise ValueError(f"{path}: intelligent evaluation dataset is empty")
    return cases


def _fact_signature(event: Event) -> tuple[str, ...]:
    return (event.project_id, event.source_id, event.observed_at.isoformat(), event.subject,
            event.predicate, event.value, event.event_type, event.effective_at.isoformat(),
            event.supersedes_event_id or "")


def _gold_signature(case: IntelligentCase, fact: GoldFact) -> tuple[str, ...]:
    return (case.source.project_id, case.source.source_id, case.source.observed_at.isoformat(),
            fact.subject, fact.predicate, fact.value, fact.event_type, fact.effective_at.isoformat(),
            fact.supersedes_event_id or "")


def _signature_dict(signature: tuple[str, ...]) -> dict[str, str | None]:
    fields = ("project_id", "source_id", "observed_at", "subject", "predicate", "value",
              "event_type", "effective_at", "supersedes_event_id")
    return {field: (value or None) for field, value in zip(fields, signature, strict=True)}


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score_extraction(case: IntelligentCase, memory: ExtractedMemory | None, *, error: str | None = None) -> dict[str, Any]:
    """Compare whole facts as sets; quote text is validated, not gold-string matched."""
    wanted = {_gold_signature(case, fact) for fact in case.expected_facts}
    events = memory.events if memory is not None else []
    found = {_fact_signature(event) for event in events}
    checks = []
    envelope_valid = memory is not None and memory.source == case.source
    for event in events:
        quote = memory.evidence_by_event.get(event.event_id)
        valid = (envelope_valid
                 and (event.project_id, event.source_id, event.observed_at)
                 == (case.source.project_id, case.source.source_id, case.source.observed_at)
                 and isinstance(quote, str) and bool(quote.strip()) and quote in case.source.text)
        checks.append({"event_id": event.event_id, "valid": valid, "quote": quote})
    matched = wanted & found
    exact = error is None and envelope_valid and wanted == found and all(check["valid"] for check in checks)
    return {
        "case_id": case.case_id,
        "passed": exact,
        "error": error,
        "source": case.source.model_dump(mode="json"),
        "expected_count": len(wanted),
        "predicted_count": len(found),
        "matched_count": len(matched),
        "precision": _rate(len(matched), len(found)),
        "recall": _rate(len(matched), len(wanted)),
        "missing_facts": [_signature_dict(item) for item in sorted(wanted - found)],
        "extra_facts": [_signature_dict(item) for item in sorted(found - wanted)],
        "quote_valid": sum(check["valid"] for check in checks),
        "quote_total": len(checks),
        "quote_checks": checks,
        "actual_events": [event.model_dump(mode="json") for event in events],
    }


def score_search_response(query: IntelligentQuery, response: dict[str, Any] | None, store: SQLiteMemoryStore, *, error: str | None = None) -> dict[str, Any]:
    """Score ranked keys and selected answer; independently audit every citation."""
    response = response if isinstance(response, dict) else {}
    raw_hits = response.get("hits", [])
    issues: list[str] = []
    if not isinstance(raw_hits, list):
        raw_hits = []
        issues.append("hits must be an array")
    if len(raw_hits) > 3:
        issues.append("search returned more than the configured top_k=3 hits")
    if response.get("project_id") != query.project_id:
        issues.append("search response project differs from requested project")
    leaked_ids: set[str] = set()
    project_leakage = response.get("project_id") is not None and response.get("project_id") != query.project_id
    keys: list[tuple[str, str] | None] = []
    results: list[QueryResult | None] = []
    checks: list[dict[str, Any]] = []
    for position, hit in enumerate(raw_hits, 1):
        keys.append(None)
        try:
            if not isinstance(hit, dict):
                raise ValueError("hit must be an object")
            subject, predicate = hit["subject"], hit["predicate"]
            fact_query = MemoryQuery(project_id=query.project_id, subject=subject, predicate=predicate,
                                     as_of=query.as_of, known_at=query.known_at)
            keys[position - 1] = fact_query.subject, fact_query.predicate
            if keys[position - 1] in keys[:position - 1]:
                issues.append("search returned a duplicate fact key")
            result = QueryResult.model_validate(hit["result"])
        except (ValueError, TypeError, KeyError):
            issues.append(f"hit {position} violates key/result schema")
            results.append(None)
            continue
        results.append(result)
        if "project_id" in hit and hit["project_id"] != query.project_id:
            project_leakage = True
            issues.append(f"hit {position} belongs to another project")
        seen: set[str] = set()
        for event in result.evidence:
            original = store.get_event(event.event_id)
            problems = []
            if original is None:
                problems.append("event missing from ledger")
            elif original.model_dump(mode="json") != event.model_dump(mode="json"):
                problems.append("citation content/source differs from ledger")
            if event.project_id != query.project_id or (original is not None and original.project_id != query.project_id):
                project_leakage = True
                leaked_ids.add(event.event_id)
                problems.append("cross-project citation")
            if (event.subject, event.predicate) != (fact_query.subject, fact_query.predicate):
                problems.append("citation outside retrieved fact key")
            if event.event_type == "plan" or event.effective_at > query.as_of:
                problems.append("citation is not an implemented fact at as_of")
            if query.known_at is not None and event.observed_at > query.known_at:
                problems.append("citation not yet observed at known_at")
            if event.event_id in seen:
                problems.append("duplicate citation")
            seen.add(event.event_id)
            checks.append({"event_id": event.event_id, "source_id": event.source_id,
                           "valid": not problems, "problems": problems})
        for event_id in result.considered_event_ids:
            original = store.get_event(event_id)
            if original is None:
                issues.append("candidate event does not exist in the ledger")
            elif original.key != fact_query.key:
                issues.append("candidate event is outside the retrieved fact scope")
            if original is not None and query.known_at is not None and original.observed_at > query.known_at:
                issues.append("candidate event is outside the known_at observation slice")
            if original is not None and original.project_id != query.project_id:
                project_leakage = True
                leaked_ids.add(event_id)
    expected_key = query.expected_key
    rank = keys.index(expected_key) + 1 if expected_key is not None and expected_key in keys else None
    recalled = not raw_hits if expected_key is None else rank is not None and rank <= 3
    top1 = not raw_hits if expected_key is None else bool(keys and keys[0] == expected_key)
    selected = results[0] if results else None
    if not raw_hits:
        actual_status, actual_value, actual_sources = "unknown", None, []
    elif selected is None:
        actual_status, actual_value, actual_sources = "invalid_result", None, []
    else:
        actual_status, actual_value = selected.status, selected.value
        actual_sources = sorted({event.source_id for event in selected.evidence})
    answer_correct = actual_status == query.expected_status and actual_value == query.expected_value
    sources_correct = set(actual_sources) == set(query.expected_source_ids)
    source_valid = all(check["valid"] for check in checks) and not issues and not project_leakage
    passed = error is None and top1 and answer_correct and sources_correct and source_valid
    if passed:
        stage = None
    elif error is not None:
        stage = "retrieval"
    elif not source_valid:
        stage = "provenance"
    elif not top1:
        stage = "retrieval"
    elif not answer_correct:
        stage = "resolution"
    else:
        stage = "provenance"
    return {
        "passed": passed,
        "failure_stage": stage,
        "error": error,
        "query": query.model_dump(mode="json"),
        "rank": rank,
        "recalled_at_3": recalled,
        "top1_correct": top1,
        "answer_correct": answer_correct,
        "sources_correct": sources_correct,
        "actual_status": actual_status,
        "actual_value": actual_value,
        "actual_source_ids": actual_sources,
        "citation_valid": sum(check["valid"] for check in checks),
        "citation_total": len(checks),
        "citation_checks": checks,
        "project_leakage": project_leakage,
        "leaked_event_ids": sorted(leaked_ids),
        "schema_issues": issues,
        "response": response,
    }


def _ledger_differs(query: IntelligentQuery, response: dict[str, Any], actual_store: SQLiteMemoryStore, gold_store: SQLiteMemoryStore) -> bool:
    keys = {query.expected_key} if query.expected_key is not None else set()
    for hit in response.get("hits", [])[:1]:
        if isinstance(hit, dict) and isinstance(hit.get("subject"), str) and isinstance(hit.get("predicate"), str):
            keys.add((hit["subject"], hit["predicate"]))
    def signatures(store: SQLiteMemoryStore) -> set[tuple[str, ...]]:
        return {_fact_signature(event) for event in store.project_events(query.project_id, known_at=query.known_at)
                if not keys or (event.subject, event.predicate) in keys}
    return signatures(actual_store) != signatures(gold_store)


def _query_metrics(scores: list[dict[str, Any]]) -> dict[str, Any]:
    keyed = [score for score in scores if score["query"]["expected_key"] is not None]
    unkeyed = [score for score in scores if score["query"]["expected_key"] is None]
    unknown = [score for score in scores if score["query"]["expected_status"] == "unknown"]
    cited = sum(score["citation_total"] for score in scores)
    valid = sum(score["citation_valid"] for score in scores)
    correct = sum(score["passed"] for score in scores)
    return {
        "total_queries": len(scores), "correct": correct, "accuracy": _rate(correct, len(scores)),
        "key_queries": len(keyed), "recalled_at_3": sum(score["recalled_at_3"] for score in keyed),
        "recall_at_3": _rate(sum(score["recalled_at_3"] for score in keyed), len(keyed)),
        "top1_key_correct": sum(score["top1_correct"] for score in keyed),
        "top1_key_accuracy": _rate(sum(score["top1_correct"] for score in keyed), len(keyed)),
        "no_key_queries": len(unkeyed), "no_key_correct": sum(score["passed"] for score in unkeyed),
        "no_key_rejection_rate": _rate(sum(score["passed"] for score in unkeyed), len(unkeyed)),
        "unknown_expected_count": len(unknown), "unknown_correct": sum(score["passed"] for score in unknown),
        "unknown_information_handling_rate": _rate(sum(score["passed"] for score in unknown), len(unknown)),
        "citation_valid": valid, "citation_total": cited, "source_validity": _rate(valid, cited),
        "project_leakage_count": sum(score["project_leakage"] for score in scores),
    }


def _metadata(provider: Any) -> dict[str, Any] | None:
    if provider is None:
        return None
    if hasattr(provider, "safe_metadata"):
        return provider.safe_metadata()
    return {"name": provider.name, "fingerprint": getattr(provider, "fingerprint", None),
            "validation_kind": "recorded_test_double"}


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _hash_input(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _implementation_hash() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _percent(value: float | None) -> str:
    return "N/A（分母为0）" if value is None else f"{value * 100:.2f}%"


def _render(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    extraction, retrieval, end_to_end = (metrics[key] for key in ("extraction", "retrieval", "end_to_end"))
    lines = [f"# 阶段目标：{report['stage_goal']}", "", f"验证状态：`{report['validation']['status']}`。{report['validation']['claim']}", "",
             "## 指标", "", "| 阶段 / 指标 | 结果 | 分子 / 分母 |", "|---|---:|---|",
             f"| 提取 Precision（完整事实） | {_percent(extraction['precision'])} | {extraction['matched_facts']} / {extraction['predicted_facts']} 预测事实 |",
             f"| 提取 Recall（完整事实） | {_percent(extraction['recall'])} | {extraction['matched_facts']} / {extraction['expected_facts']} 标准事实 |",
             f"| 提取案例全对 | {_percent(extraction['exact_case_accuracy'])} | {extraction['exact_cases']} / {extraction['total_cases']} 案例 |",
             f"| 人工事件检索 Recall@3 | {_percent(retrieval['recall_at_3'])} | {retrieval['recalled_at_3']} / {retrieval['key_queries']} 有标准事实键的查询 |",
             f"| 人工事件 Top1 键命中 | {_percent(retrieval['top1_key_accuracy'])} | {retrieval['top1_key_correct']} / {retrieval['key_queries']} 有标准事实键的查询 |",
             f"| 人工事件最终答案全对 | {_percent(retrieval['accuracy'])} | {retrieval['correct']} / {retrieval['total_queries']} 查询 |",
             f"| 端到端最终答案全对 | {_percent(end_to_end['accuracy'])} | {end_to_end['correct']} / {end_to_end['total_queries']} 查询 |",
             f"| 端到端未知信息处理 | {_percent(end_to_end['unknown_information_handling_rate'])} | {end_to_end['unknown_correct']} / {end_to_end['unknown_expected_count']} 预期 unknown 查询 |",
             f"| 原文引用与来源合法性（各阶段累计） | {_percent(metrics['source_validity'])} | {metrics['source_valid_checks']} / {metrics['source_total_checks']} 检查 |",
             f"| 跨项目串用 | {metrics['project_leakage_count']} | 含串用的查询数 |",
             f"| 全用例严格通过 | {metrics['all_passed']} | 每个提取案例 + 两条查询路径均全对 |",
             f"| 数值发布门槛 | {metrics['release_gate_passed']} | 外部 pytest 与真实服务验证须另验 |",
             f"| 运行耗时 | {metrics['runtime_seconds']:.6f}s | 含提取、导入、索引、查询和评分；不含报告写入 |", "",
             "## 预先固定的门槛", "", "```json", json.dumps(report["config"]["release_thresholds"], ensure_ascii=False, indent=2), "```", "",
             "## 失败案例", ""]
    if not report["failures"]:
        lines.append("无失败案例。")
    else:
        for failure in report["failures"]:
            lines.extend([f"### {failure['stage']} / {failure['case_id']}", "", "```json", json.dumps(failure, ensure_ascii=False, indent=2), "```", ""])
    lines.extend(["", "## 配置与复现证据", "", "```json", json.dumps(report["config"], ensure_ascii=False, indent=2), "```", "", "## 边界", "",
                  "- 录制提取响应和录制向量是人工测试替身，不代表真实语言理解或语义检索质量。真实 chat 配合 lexical 也不能证明 Embedding 效果。",
                  "- 引文只要求是原文中的精确片段，不要求与单一标准引文逐字相同。片段存在不证明模型的语义解释必然正确。",
                  "- 检索路径使用人工事件；端到端路径仅从 seeds 和本次真实提取结果构建，不复制标准事件。所有案例先导入完毕，再按查询时间切片评分。",
                  "- 来源合法性只验证账本一致性、项目与事实键、时间和原文片段，不认证外部来源真实性。",
                  "- 微平均提取 Precision/Recall 比较完整事实集合（含类型、时间和纠错目标）；所有零分母指标显示 N/A。",
                  "- all_passed 比数值门槛严格。release_gate_passed 只报告既定数值门槛，不能替代外部核心回归或独立保留集和真实模型验收。",
                  "- 这批合成样本很小；时间戳、环境路径、耗时和实际模型响应可变，不构成生产可靠性保证。", ""])
    return "\n".join(lines)


def run_intelligent_evaluation(seeds_path: str | Path, gold_events_path: str | Path,
                               dataset_path: str | Path, output_path: str | Path, *,
                               responses_path: str | Path | None, vectors_path: str | Path | None = None,
                               live: bool = False, search_mode: str = "lexical", min_cosine: float = 0.2) -> dict[str, Any]:
    """Run three independent stages, emitting auditable JSON and Markdown reports."""
    started = perf_counter()
    seeds_path, gold_events_path, dataset_path, output_path = map(Path, (seeds_path, gold_events_path, dataset_path, output_path))
    if search_mode not in {"lexical", "semantic", "hybrid"}:
        raise ValueError("search_mode must be lexical, semantic, or hybrid")
    from repomind.intelligence.config import search_min_cosine
    min_cosine = search_min_cosine(min_cosine, read_file=False)
    if output_path.suffix.lower() not in {".json", ".md"}:
        raise ValueError("intelligent evaluation output must end in .json or .md")
    responses = Path(responses_path) if responses_path is not None else None
    vectors = Path(vectors_path) if vectors_path is not None else None
    inputs = [seeds_path, gold_events_path, dataset_path] + ([responses] if responses is not None else []) + ([vectors] if vectors is not None else [])
    if {output_path.with_suffix(suffix).resolve() for suffix in (".md", ".json")} & {path.resolve() for path in inputs}:
        raise ValueError("evaluation reports must not overwrite source datasets or replay artifacts")
    cases = load_intelligent_cases(dataset_path)
    if live:
        settings = ProviderConfig.from_env()
        if settings.api_key is None or settings.chat_model is None:
            raise ValueError("live extraction requires a configured chat API key and chat model")
        provider = OpenAICompatibleProvider(settings)
    else:
        if responses is None:
            raise ValueError("offline extraction requires responses_path for recorded replay")
        provider = ReplayExtractionProvider(responses)
    embedder = None
    if search_mode != "lexical":
        if vectors is not None:
            embedder = RecordedEmbedder(vectors)
        elif live:
            from repomind.intelligence.dashscope import embedding_provider_from_env
            embedder = embedding_provider_from_env()
        else:
            raise ValueError("offline semantic/hybrid evaluation requires recorded vectors_path")

    extraction_scores: list[dict[str, Any]] = []
    query_scores: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="repomind-intelligent-eval-") as directory:
        with SQLiteMemoryStore(Path(directory) / "gold.sqlite3") as gold_store, SQLiteMemoryStore(Path(directory) / "actual.sqlite3") as actual_store:
            gold_store.import_jsonl(gold_events_path)
            actual_store.import_jsonl(seeds_path)
            extractor = Extractor(provider)
            # Never supply expected_facts or the gold ledger to the provider.
            for case in cases:
                memory, error = None, None
                try:
                    context = actual_store.project_events(case.source.project_id)
                    memory = extractor.extract(case.source, context)
                    actual_store.import_extractions([memory])
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                score = score_extraction(case, memory, error=error)
                extraction_scores.append(score)
                if not score["passed"]:
                    failures.append({"stage": "extraction", "case_id": case.case_id, "details": score})
            gold_search, actual_search = HybridMemorySearch(gold_store, embedder), HybridMemorySearch(actual_store, embedder)
            for case in cases:
                for number, query in enumerate(case.queries, 1):
                    pair: dict[str, Any] = {"case_id": case.case_id, "query_index": number}
                    for stage, search, store in [("retrieval", gold_search, gold_store), ("end_to_end", actual_search, actual_store)]:
                        response, error = {}, None
                        try:
                            if search_mode != "lexical":
                                search.index(query.project_id, known_at=query.known_at)
                            response = search.search(query.project_id, query.text, query.as_of,
                                                     known_at=query.known_at, top_k=3, mode=search_mode, min_cosine=min_cosine)
                        except Exception as exc:
                            error = f"{type(exc).__name__}: {exc}"
                        score = score_search_response(query, response, store, error=error)
                        if stage == "end_to_end" and not score["passed"]:
                            differs = _ledger_differs(query, response, actual_store, gold_store)
                            score["extraction_ledger_differs"] = differs
                            score["failure_stage"] = "extraction" if differs else score["failure_stage"]
                        pair[stage] = score
                        if not score["passed"]:
                            failures.append({"stage": stage, "case_id": case.case_id, "query_index": number, "details": score})
                    query_scores.append(pair)

    elapsed = perf_counter() - started
    expected_count = sum(score["expected_count"] for score in extraction_scores)
    predicted_count = sum(score["predicted_count"] for score in extraction_scores)
    matched_count = sum(score["matched_count"] for score in extraction_scores)
    exact_cases = sum(score["passed"] for score in extraction_scores)
    extraction_metrics = {
        "expected_facts": expected_count, "predicted_facts": predicted_count, "matched_facts": matched_count,
        "precision": _rate(matched_count, predicted_count), "recall": _rate(matched_count, expected_count),
        "exact_cases": exact_cases, "total_cases": len(cases), "exact_case_accuracy": _rate(exact_cases, len(cases)),
        "abstention_cases": sum(not case.expected_facts for case in cases),
        "correct_abstentions": sum(score["passed"] for case, score in zip(cases, extraction_scores, strict=True) if not case.expected_facts),
        "quote_valid": sum(score["quote_valid"] for score in extraction_scores),
        "quote_total": sum(score["quote_total"] for score in extraction_scores),
    }
    retrieval_metrics = _query_metrics([pair["retrieval"] for pair in query_scores])
    end_to_end_metrics = _query_metrics([pair["end_to_end"] for pair in query_scores])
    source_valid = extraction_metrics["quote_valid"] + retrieval_metrics["citation_valid"] + end_to_end_metrics["citation_valid"]
    source_total = extraction_metrics["quote_total"] + retrieval_metrics["citation_total"] + end_to_end_metrics["citation_total"]
    source_validity = _rate(source_valid, source_total)
    leakage = retrieval_metrics["project_leakage_count"] + end_to_end_metrics["project_leakage_count"]
    def at_least(value: float | None, threshold: float) -> bool:
        return value is not None and value >= threshold
    gate_checks = {
        "extraction_precision": at_least(extraction_metrics["precision"], RELEASE_THRESHOLDS["extraction_precision_min"]),
        "extraction_recall": at_least(extraction_metrics["recall"], RELEASE_THRESHOLDS["extraction_recall_min"]),
        "gold_retrieval_recall_at_3": at_least(retrieval_metrics["recall_at_3"], RELEASE_THRESHOLDS["gold_retrieval_recall_at_3_min"]),
        "end_to_end_accuracy": at_least(end_to_end_metrics["accuracy"], RELEASE_THRESHOLDS["end_to_end_accuracy_min"]),
        "source_validity": source_validity == RELEASE_THRESHOLDS["source_validity_required"],
        "project_leakage": leakage <= RELEASE_THRESHOLDS["project_leakage_max"],
    }
    real_semantic = live and search_mode != "lexical" and vectors is None
    validation = {
        "status": "live_pipeline_measured" if real_semantic else "partial",
        "offline_test_double": not live or (search_mode != "lexical" and vectors is not None),
        "live_extraction": live,
        "real_semantic_quality": real_semantic,
        "recorded_extraction": not live,
        "recorded_embeddings": search_mode != "lexical" and vectors is not None,
        "search_mode": search_mode,
        "core_tests": "not executed by this runner; require separate pytest evidence",
        "release_gate_scope": "predeclared numeric metrics only; independent holdout, core regression, and real services require separate acceptance",
        "claim": ("真实提取与独立 Embedding 流水线已测量；完整发布仍需外部核心回归与独立保留集验收。" if real_semantic else
                  "已测量真实聊天提取与当前检索路径；真实 Embedding 效果尚未验收。" if live else
                  "离线人工响应/向量回放仅验证工程逻辑，真实提取和语义质量尚未验收。"),
    }
    used_inputs = {"seeds": _hash_input(seeds_path), "gold_events": _hash_input(gold_events_path), "dataset": _hash_input(dataset_path)}
    if not live:
        used_inputs["recorded_extraction"] = _hash_input(responses)
    if vectors is not None and search_mode != "lexical":
        used_inputs["recorded_vectors"] = _hash_input(vectors)
    report = {
        "stage_goal": STAGE_GOAL,
        "report_version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation": validation,
        "metrics": {
            "all_passed": exact_cases == len(cases) and all(pair[stage]["passed"] for pair in query_scores for stage in ("retrieval", "end_to_end")),
            "release_gate_passed": all(gate_checks.values()), "gate_checks": gate_checks,
            "extraction": extraction_metrics, "retrieval": retrieval_metrics, "end_to_end": end_to_end_metrics,
            "source_validity": source_validity, "source_valid_checks": source_valid, "source_total_checks": source_total,
            "project_leakage_count": leakage, "runtime_seconds": elapsed,
            "failure_stage_counts": dict(sorted(Counter(failure["details"].get("failure_stage") or failure["stage"] for failure in failures).items())),
        },
        "config": {
            "inputs": used_inputs, "dataset_split": dataset_path.parent.name,
            "python_version": platform.python_version(), "repomind_source_version": __version__,
            "implementation_sha256": _implementation_hash(),
            "repomind_installed_version": _version("repomind"), "pydantic_version": _version("pydantic"), "sqlite_version": sqlite3.sqlite_version,
            "extraction_provider": _metadata(provider), "embedding_provider": _metadata(embedder),
            "search_mode": search_mode, "top_k": 3, "min_cosine": min_cosine,
            "ingestion_policy": "ingest every split source into seeds-only actual ledger before any query; gold retrieval ledger is separate",
            "extraction_scoring": "whole fact set including trusted source/project/observation, effective time, type, correction target; exact source substring independently audited",
            "query_scoring": "ranked key + top1 status/value + exact source-ID set + every cited ledger event valid",
            "zero_denominator_policy": "null/N/A; lack of positive samples does not satisfy a numeric release gate",
            "release_thresholds": dict(RELEASE_THRESHOLDS),
            "semantic_claim_boundary": "recorded vectors and lexical search cannot establish real embedding quality",
        },
        "extraction_cases": extraction_scores,
        "query_cases": query_scores,
        "failures": failures,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path.with_suffix(".md").write_text(_render(report), encoding="utf-8")
    return report
