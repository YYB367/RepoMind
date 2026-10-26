# RepoMind V1 evaluation report

Strategy: `v1_temporal_rules`. Generated UTC: `2026-10-26T11:07:49.034437+00:00`.

A question passes only when every structured query has the correct status, value, exact evidence set, and valid citations.

| Metric | Result | Denominator / unit |
|---|---:|---|
| Strict question accuracy | 100.00% | 16 / 16 questions |
| Status/value question accuracy | 100.00% | 16 questions |
| Unknown-information handling | 100.00% | 3 / 3 expected-unknown queries |
| Refusal correctness (unknown + conflict) | 100.00% | 5 / 5 expected-refusal queries |
| Cross-project leakage | 0 | queries with an out-of-project candidate/citation |
| Source citation validity | 100.00% | 25 / 25 citations |
| Exact expected evidence | 100.00% | 24 / 24 queries |
| Runtime | 0.042209 | seconds, validation + temporary DB import + queries + scoring; report I/O excluded |

## Categories

| Category | Passed / total | Strict accuracy |
|---|---:|---:|
| basic | 2 / 2 | 100.00% |
| cross_session | 2 / 2 | 100.00% |
| isolation | 3 / 3 | 100.00% |
| state | 3 / 3 | 100.00% |
| temporal | 3 / 3 | 100.00% |
| unknown | 3 / 3 | 100.00% |

## Failures

None.

## Configuration

```json
{
  "events_path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\fixtures\\conversations.jsonl",
  "dataset_path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\holdout\\questions.jsonl",
  "events_sha256": "4542212c9842d1ba32a10fa492eed573db56bb77698d7bb68fb4ecd13e8bac69",
  "dataset_sha256": "7eb44b226979fbe1b48c35ffe69124d3f4e87d63caf3ef018bdc1eed46c0be7d",
  "python_version": "3.12.14",
  "repomind_version": "1.0.0",
  "pydantic_version": "2.14.1",
  "sqlite_version": "3.53.1",
  "database": "fresh temporary SQLite; removed after scoring",
  "import": {
    "imported": 60,
    "duplicates": 0
  },
  "scoring": "all queries: exact status/value + exact event ID set + ledger citation validity",
  "date_policy": "date-only queries mean end-of-day UTC; known_at is optional",
  "baseline_policy": "same scope; observed_at<=as_of and known_at if given; max(observed_at,event_id); ignores event_type/effective_at/correction links",
  "failure_stage_precedence": [
    "invalid provenance",
    "missing retrieval candidates",
    "incorrect resolution",
    "wrong evidence selection"
  ],
  "project_leakage_unit": "number of queries containing any out-of-project candidate/citation"
}
```

## Limits

- The 48 synthetic questions and 16-question holdout are small; success does not establish production reliability or natural-language memory quality.
- Cross-session cases are conjunctions of explicit structured queries. There is no semantic retrieval, LLM, token-cost estimate, or code agent.
- Source validity checks ledger consistency, project/fact scope, effective time, known-at visibility, non-plan evidence, and duplicate citations. It does not externally authenticate source documents.
- Repeated runs preserve semantic results; generated timestamps, environment paths, and measured runtime can differ.
- The latest-observation baseline is a deterministic negative control, not an implementation of Mem0 or an empirical comparison with a third-party product.
