"""Strict, independently testable answer and provenance scoring.

Gold answers are never supplied to the memory implementation. Citation validity
and agreement with the gold evidence are deliberately separate measurements.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from repomind.domain.models import MemoryQuery, QueryResult


def score_answer(
    query: MemoryQuery,
    expected: Mapping[str, Any],
    actual: QueryResult,
    store: Any,
) -> dict[str, Any]:
    """Score one query, including audit checks against the stored event ledger.

    Failure precedence is invalid provenance, missing retrieval candidates,
    incorrect resolution, then a mismatch in the selected evidence. An unknown
    gold answer has no evidence, so an incorrect refusal is a resolution error.
    """
    gold = dict(expected)
    wanted_ids = set(gold["event_ids"])
    cited_ids = [event.event_id for event in actual.evidence]
    considered_ids = set(actual.considered_event_ids)
    issues: list[dict[str, str]] = []
    valid_citations = 0
    leaked_ids: set[str] = set()
    seen: set[str] = set()

    for event in actual.evidence:
        problems: list[str] = []
        original = store.get_event(event.event_id)
        if original is None:
            problems.append("event does not exist in the ledger")
        elif original.model_dump(mode="json") != event.model_dump(mode="json"):
            problems.append("citation content/source differs from stored event")
        if event.project_id != query.project_id or (original is not None and original.project_id != query.project_id):
            leaked_ids.add(event.event_id)
            problems.append("cross-project citation")
        if (event.subject, event.predicate) != (query.subject, query.predicate):
            problems.append("citation is outside the requested fact key")
        if event.effective_at > query.as_of:
            problems.append("citation is not effective at as_of")
        if query.known_at is not None and event.observed_at > query.known_at:
            problems.append("citation was not observed by known_at")
        if event.event_type == "plan":
            problems.append("plan cannot support an implemented fact")
        if event.event_id in seen:
            problems.append("duplicate citation")
        seen.add(event.event_id)
        if problems:
            issues.append({"event_id": event.event_id, "reason": "; ".join(problems)})
        else:
            valid_citations += 1

    # A retriever must not inspect other projects even when its final answer
    # happens to discard those candidates.
    for event_id in considered_ids:
        candidate = store.get_event(event_id)
        if candidate is not None and candidate.project_id != query.project_id:
            leaked_ids.add(event_id)

    answer_correct = actual.status == gold["status"] and actual.value == gold["value"]
    evidence_correct = set(cited_ids) == wanted_ids and len(cited_ids) == len(wanted_ids)
    provenance_correct = not issues and not leaked_ids
    passed = answer_correct and evidence_correct and provenance_correct
    if passed:
        stage = None
    elif not provenance_correct:
        stage = "provenance"
    elif not wanted_ids.issubset(considered_ids):
        stage = "retrieval"
    elif not answer_correct:
        stage = "resolution"
    else:
        stage = "provenance"

    return {
        "passed": passed,
        "answer_correct": answer_correct,
        "evidence_correct": evidence_correct,
        "provenance_correct": provenance_correct,
        "failure_stage": stage,
        "query": query.model_dump(mode="json"),
        "expected": gold,
        "actual": actual.model_dump(mode="json"),
        "citation_valid": valid_citations,
        "citation_total": len(cited_ids),
        "citation_issues": issues,
        "project_leakage": bool(leaked_ids),
        "leaked_event_ids": sorted(leaked_ids),
        "missing_candidate_event_ids": sorted(wanted_ids - considered_ids),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def summarize(cases: list[dict[str, Any]], runtime_seconds: float) -> dict[str, Any]:
    """Aggregate question-level accuracy and query/citation-level diagnostics."""
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_category[case["category"]].append(case)
    answers = [answer for case in cases for answer in case["answers"]]
    unknown = [a for a in answers if a["expected"]["status"] == "unknown"]
    refusals = [a for a in answers if a["expected"]["status"] != "ok"]
    citation_valid = sum(a["citation_valid"] for a in answers)
    citation_total = sum(a["citation_total"] for a in answers)
    evidence_correct = sum(a["evidence_correct"] for a in answers)
    correct = sum(case["passed"] for case in cases)
    unknown_correct = sum(a["passed"] for a in unknown)
    refusal_correct = sum(a["passed"] for a in refusals)
    return {
        "total": len(cases),
        "correct": correct,
        "accuracy": _rate(correct, len(cases)),
        "answer_accuracy": _rate(sum(all(a["answer_correct"] for a in c["answers"]) for c in cases), len(cases)),
        "categories": {
            category: {
                "total": len(items),
                "correct": sum(item["passed"] for item in items),
                "accuracy": _rate(sum(item["passed"] for item in items), len(items)),
            }
            for category, items in sorted(by_category.items())
        },
        "query_total": len(answers),
        "unknown_correct": unknown_correct,
        "unknown_expected_count": len(unknown),
        "unknown_information_handling_rate": _rate(unknown_correct, len(unknown)),
        "refusal_correct": refusal_correct,
        "refusal_expected_count": len(refusals),
        "refusal_correctness": _rate(refusal_correct, len(refusals)),
        "project_leakage_count": sum(a["project_leakage"] for a in answers),
        "citation_valid": citation_valid,
        "citation_total": citation_total,
        "source_citation_correctness": _rate(citation_valid, citation_total),
        "evidence_match_count": evidence_correct,
        "evidence_match_rate": _rate(evidence_correct, len(answers)),
        "runtime_seconds": runtime_seconds,
    }
