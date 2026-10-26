"""Fixed JSONL evaluation, a naive baseline, and reproducible audit reports."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import MemoryQuery, QueryResult
from repomind.evaluation.metrics import score_answer, summarize
from repomind.memory.retriever import MemoryRetriever


class ExpectedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok", "unknown", "insufficient_evidence"]
    value: str | None
    event_ids: list[Annotated[str, Field(min_length=1)]]

    @model_validator(mode="after")
    def consistent(self) -> "ExpectedAnswer":
        if len(self.event_ids) != len(set(self.event_ids)):
            raise ValueError("expected event_ids must be unique")
        if self.status == "ok" and (not self.value or not self.event_ids):
            raise ValueError("an ok answer needs a nonempty value and evidence")
        if self.status != "ok" and self.value is not None:
            raise ValueError("a refusal must have value=null")
        if self.status == "unknown" and self.event_ids:
            raise ValueError("an unknown answer cannot cite fact evidence")
        return self


class EvaluationQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: Annotated[str, Field(min_length=1)]
    category: Literal["basic", "temporal", "state", "cross_session", "isolation", "unknown"]
    description: Annotated[str, Field(min_length=1)]
    queries: Annotated[list[MemoryQuery], Field(min_length=1)]
    expected: Annotated[list[ExpectedAnswer], Field(min_length=1)]

    @model_validator(mode="after")
    def same_arity(self) -> "EvaluationQuestion":
        if len(self.queries) != len(self.expected):
            raise ValueError("queries and expected must have the same length")
        return self


def load_questions(path: Path) -> list[EvaluationQuestion]:
    questions: list[EvaluationQuestion] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                    result: dict[str, Any] = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError(f"duplicate JSON key {key!r}")
                        result[key] = value
                    return result

                question = EvaluationQuestion.model_validate(json.loads(line, object_pairs_hook=unique_keys))
                if question.question_id in seen:
                    raise ValueError(f"duplicate question_id {question.question_id!r}")
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
            seen.add(question.question_id)
            questions.append(question)
    if not questions:
        raise ValueError(f"{path}: evaluation dataset is empty")
    return questions


def _baseline_query(store: SQLiteMemoryStore, query: MemoryQuery) -> QueryResult:
    # Deliberately naive negative control: same scope, latest observation known
    # by as_of. It does not understand plan, effective time, or correction links.
    candidates = [event for event in store.list_events(query) if event.observed_at <= query.as_of]
    considered = sorted(event.event_id for event in candidates)
    if not candidates:
        return QueryResult(status="unknown", value=None, reason="baseline: no observed record", evidence=[], considered_event_ids=considered)
    chosen = max(candidates, key=lambda event: (event.observed_at, event.event_id))
    return QueryResult(status="ok", value=chosen.value, reason="baseline: latest observation; ignores event type/effective time", evidence=[chosen], considered_event_ids=considered)


def _version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "source-checkout (not installed)"


def _percent(value: float | None) -> str:
    return "N/A (zero denominator)" if value is None else f"{100 * value:.2f}%"


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    config = report["config"]
    lines = [
        "# RepoMind V1 evaluation report",
        "",
        f"Strategy: `{report['strategy']}`. Generated UTC: `{report['generated_at']}`.",
        "",
        "A question passes only when every structured query has the correct status, value, exact evidence set, and valid citations.",
        "",
        "| Metric | Result | Denominator / unit |",
        "|---|---:|---|",
        f"| Strict question accuracy | {_percent(metrics['accuracy'])} | {metrics['correct']} / {metrics['total']} questions |",
        f"| Status/value question accuracy | {_percent(metrics['answer_accuracy'])} | {metrics['total']} questions |",
        f"| Unknown-information handling | {_percent(metrics['unknown_information_handling_rate'])} | {metrics['unknown_correct']} / {metrics['unknown_expected_count']} expected-unknown queries |",
        f"| Refusal correctness (unknown + conflict) | {_percent(metrics['refusal_correctness'])} | {metrics['refusal_correct']} / {metrics['refusal_expected_count']} expected-refusal queries |",
        f"| Cross-project leakage | {metrics['project_leakage_count']} | queries with an out-of-project candidate/citation |",
        f"| Source citation validity | {_percent(metrics['source_citation_correctness'])} | {metrics['citation_valid']} / {metrics['citation_total']} citations |",
        f"| Exact expected evidence | {_percent(metrics['evidence_match_rate'])} | {metrics['evidence_match_count']} / {metrics['query_total']} queries |",
        f"| Runtime | {metrics['runtime_seconds']:.6f} | seconds, validation + temporary DB import + queries + scoring; report I/O excluded |",
        "",
        "## Categories",
        "",
        "| Category | Passed / total | Strict accuracy |",
        "|---|---:|---:|",
    ]
    for category, item in metrics["categories"].items():
        lines.append(f"| {_cell(category)} | {item['correct']} / {item['total']} | {_percent(item['accuracy'])} |")
    lines.extend(["", "## Failures", ""])
    if not report["failures"]:
        lines.append("None.")
    for failure in report["failures"]:
        lines.extend([f"### {_cell(failure['question_id'])}: {_cell(failure['description'])}", ""])
        for index, answer in enumerate(failure["answers"], 1):
            if answer["passed"]:
                continue
            lines.extend([
                f"Query {index}, stage: `{answer['failure_stage']}`.",
                "",
                "```json",
                json.dumps({key: answer[key] for key in ["query", "expected", "actual", "citation_issues", "missing_candidate_event_ids", "leaked_event_ids"]}, ensure_ascii=False, indent=2),
                "```",
                "",
            ])
    lines.extend(["", "## Configuration", "", "```json", json.dumps(config, ensure_ascii=False, indent=2), "```", "", "## Limits", ""])
    lines.extend([
        "- The 48 synthetic questions and 16-question holdout are small; success does not establish production reliability or natural-language memory quality.",
        "- Cross-session cases are conjunctions of explicit structured queries. There is no semantic retrieval, LLM, token-cost estimate, or code agent.",
        "- Source validity checks ledger consistency, project/fact scope, effective time, known-at visibility, non-plan evidence, and duplicate citations. It does not externally authenticate source documents.",
        "- Repeated runs preserve semantic results; generated timestamps, environment paths, and measured runtime can differ.",
        "- The latest-observation baseline is a deterministic negative control, not an implementation of Mem0 or an empirical comparison with a third-party product.",
        "",
    ])
    return "\n".join(lines)


def run_evaluation(events_path: Path, dataset_path: Path, output_path: Path, *, baseline: bool = False) -> dict[str, Any]:
    """Evaluate a fixed dataset in a disposable database and write MD plus JSON."""
    events_path, dataset_path, output_path = map(Path, (events_path, dataset_path, output_path))
    if output_path.suffix.lower() not in {".md", ".json"}:
        raise ValueError("evaluation --output must end in .md or .json")
    md_path, json_path = output_path.with_suffix(".md"), output_path.with_suffix(".json")
    if {md_path.resolve(), json_path.resolve()} & {events_path.resolve(), dataset_path.resolve()}:
        raise ValueError("evaluation output must not overwrite an input file")
    started = perf_counter()
    questions = load_questions(dataset_path)
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="repomind-eval-") as directory:
        with SQLiteMemoryStore(Path(directory) / "memory.sqlite3") as store:
            imported = store.import_jsonl(events_path)
            retriever = MemoryRetriever(store)
            for question in questions:
                case_started = perf_counter()
                answers = []
                for query, expected in zip(question.queries, question.expected, strict=True):
                    actual = _baseline_query(store, query) if baseline else retriever.query(query)
                    answers.append(score_answer(query, expected.model_dump(), actual, store))
                cases.append({
                    "question_id": question.question_id,
                    "category": question.category,
                    "description": question.description,
                    "passed": all(answer["passed"] for answer in answers),
                    "answers": answers,
                    "runtime_seconds": perf_counter() - case_started,
                })
    elapsed = perf_counter() - started
    report = {
        "report_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "latest_observation_baseline" if baseline else "v1_temporal_rules",
        "config": {
            "events_path": str(events_path.resolve()),
            "dataset_path": str(dataset_path.resolve()),
            "events_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
            "dataset_sha256": hashlib.sha256(dataset_path.read_bytes()).hexdigest(),
            "python_version": platform.python_version(),
            "repomind_version": _version("repomind"),
            "pydantic_version": _version("pydantic"),
            "sqlite_version": sqlite3.sqlite_version,
            "database": "fresh temporary SQLite; removed after scoring",
            "import": imported.model_dump() if hasattr(imported, "model_dump") else str(imported),
            "scoring": "all queries: exact status/value + exact event ID set + ledger citation validity",
            "date_policy": "date-only queries mean end-of-day UTC; known_at is optional",
            "baseline_policy": "same scope; observed_at<=as_of and known_at if given; max(observed_at,event_id); ignores event_type/effective_at/correction links",
            "failure_stage_precedence": ["invalid provenance", "missing retrieval candidates", "incorrect resolution", "wrong evidence selection"],
            "project_leakage_unit": "number of queries containing any out-of-project candidate/citation",
        },
        "metrics": summarize(cases, elapsed),
        "failures": [case for case in cases if not case["passed"]],
        "cases": cases,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return report
