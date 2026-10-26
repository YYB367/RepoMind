# RepoMind V1 evaluation report

Strategy: `latest_observation_baseline`. Generated UTC: `2026-10-26T11:08:45.859994+00:00`.

A question passes only when every structured query has the correct status, value, exact evidence set, and valid citations.

| Metric | Result | Denominator / unit |
|---|---:|---|
| Strict question accuracy | 50.00% | 8 / 16 questions |
| Status/value question accuracy | 56.25% | 16 questions |
| Unknown-information handling | 100.00% | 3 / 3 expected-unknown queries |
| Refusal correctness (unknown + conflict) | 60.00% | 3 / 5 expected-refusal queries |
| Cross-project leakage | 0 | queries with an out-of-project candidate/citation |
| Source citation validity | 78.95% | 15 / 19 citations |
| Exact expected evidence | 62.50% | 15 / 24 queries |
| Runtime | 0.041311 | seconds, validation + temporary DB import + queries + scoring; report I/O excluded |

## Categories

| Category | Passed / total | Strict accuracy |
|---|---:|---:|
| basic | 2 / 2 | 100.00% |
| cross_session | 0 / 2 | 0.00% |
| isolation | 2 / 3 | 66.67% |
| state | 1 / 3 | 33.33% |
| temporal | 0 / 3 | 0.00% |
| unknown | 3 / 3 | 100.00% |

## Failures

### H-T01: 迟到观察不改变实际生效边界的包含关系。

Query 1, stage: `provenance`.

```json
{
  "query": {
    "project_id": "BuildPilot",
    "subject": "project",
    "predicate": "database",
    "as_of": "2026-03-15T00:00:00Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "MySQL",
    "event_ids": [
      "B06"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "MySQL",
    "evidence": [
      {
        "event_id": "B05",
        "project_id": "BuildPilot",
        "subject": "project",
        "predicate": "database",
        "value": "MySQL",
        "event_type": "plan",
        "observed_at": "2026-02-10T00:00:00Z",
        "effective_at": "2026-03-15T00:00:00Z",
        "source_id": "build-session-03",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "B01",
      "B05"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [
    {
      "event_id": "B05",
      "reason": "plan cannot support an implemented fact"
    }
  ],
  "missing_candidate_event_ids": [
    "B06"
  ],
  "leaked_event_ids": []
}
```

### H-T02: 精确时间在完成生效之前一秒。

Query 1, stage: `provenance`.

```json
{
  "query": {
    "project_id": "BuildPilot",
    "subject": "project",
    "predicate": "database",
    "as_of": "2026-03-14T23:59:59Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "PostgreSQL",
    "event_ids": [
      "B01"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "MySQL",
    "evidence": [
      {
        "event_id": "B05",
        "project_id": "BuildPilot",
        "subject": "project",
        "predicate": "database",
        "value": "MySQL",
        "event_type": "plan",
        "observed_at": "2026-02-10T00:00:00Z",
        "effective_at": "2026-03-15T00:00:00Z",
        "source_id": "build-session-03",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "B01",
      "B05"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [
    {
      "event_id": "B05",
      "reason": "citation is not effective at as_of; plan cannot support an implemented fact"
    }
  ],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### H-T03: 使用观察截止时间保留迟到记录之前的知识。

Query 1, stage: `provenance`.

```json
{
  "query": {
    "project_id": "BuildPilot",
    "subject": "project",
    "predicate": "database",
    "as_of": "2026-03-15T23:59:59.999999Z",
    "known_at": "2026-03-19T23:59:59Z"
  },
  "expected": {
    "status": "ok",
    "value": "PostgreSQL",
    "event_ids": [
      "B01"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "MySQL",
    "evidence": [
      {
        "event_id": "B05",
        "project_id": "BuildPilot",
        "subject": "project",
        "predicate": "database",
        "value": "MySQL",
        "event_type": "plan",
        "observed_at": "2026-02-10T00:00:00Z",
        "effective_at": "2026-03-15T00:00:00Z",
        "source_id": "build-session-03",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "B01",
      "B05"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [
    {
      "event_id": "B05",
      "reason": "plan cannot support an implemented fact"
    }
  ],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### H-S02: 只依据已观察到的相互冲突队列事件拒答。

Query 1, stage: `retrieval`.

```json
{
  "query": {
    "project_id": "BuildPilot",
    "subject": "project",
    "predicate": "queue",
    "as_of": "2026-02-01T23:59:59.999999Z",
    "known_at": "2026-02-03T23:59:59.999999Z"
  },
  "expected": {
    "status": "insufficient_evidence",
    "value": null,
    "event_ids": [
      "B13",
      "B14"
    ]
  },
  "actual": {
    "status": "unknown",
    "value": null,
    "evidence": [],
    "reason": "baseline: no observed record",
    "considered_event_ids": [],
    "plan_event_ids": []
  },
  "citation_issues": [],
  "missing_candidate_event_ids": [
    "B13",
    "B14"
  ],
  "leaked_event_ids": []
}
```

### H-S03: 后续纠错消除冲突且保留同值证据。

Query 1, stage: `retrieval`.

```json
{
  "query": {
    "project_id": "BuildPilot",
    "subject": "project",
    "predicate": "queue",
    "as_of": "2026-02-01T23:59:59.999999Z",
    "known_at": "2026-02-04T23:59:59.999999Z"
  },
  "expected": {
    "status": "ok",
    "value": "NATS",
    "event_ids": [
      "B13",
      "B15"
    ]
  },
  "actual": {
    "status": "unknown",
    "value": null,
    "evidence": [],
    "reason": "baseline: no observed record",
    "considered_event_ids": [],
    "plan_event_ids": []
  },
  "citation_issues": [],
  "missing_candidate_event_ids": [
    "B13",
    "B15"
  ],
  "leaked_event_ids": []
}
```

### H-C01: 联合三个会话事实并忽略尚未完成的 CI 计划。

Query 3, stage: `provenance`.

```json
{
  "query": {
    "project_id": "BuildPilot",
    "subject": "project",
    "predicate": "ci",
    "as_of": "2026-04-20T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "Jenkins",
    "event_ids": [
      "B07"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "CircleCI",
    "evidence": [
      {
        "event_id": "B18",
        "project_id": "BuildPilot",
        "subject": "project",
        "predicate": "ci",
        "value": "CircleCI",
        "event_type": "plan",
        "observed_at": "2026-03-01T00:00:00Z",
        "effective_at": "2026-04-01T00:00:00Z",
        "source_id": "build-session-14",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "B07",
      "B18"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [
    {
      "event_id": "B18",
      "reason": "plan cannot support an implemented fact"
    }
  ],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### H-C02: 以当前知识联合重建三个会话的历史配置。

Query 1, stage: `retrieval`.

```json
{
  "query": {
    "project_id": "BuildPilot",
    "subject": "project",
    "predicate": "workers",
    "as_of": "2026-01-20T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "8",
    "event_ids": [
      "B09"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "4",
    "evidence": [
      {
        "event_id": "B08",
        "project_id": "BuildPilot",
        "subject": "project",
        "predicate": "workers",
        "value": "4",
        "event_type": "declare",
        "observed_at": "2026-01-08T00:00:00Z",
        "effective_at": "2026-01-08T00:00:00Z",
        "source_id": "build-session-05",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "B08"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [],
  "missing_candidate_event_ids": [
    "B09"
  ],
  "leaked_event_ids": []
}
```

### H-I03: 别的项目的区域同值佐证不能掩盖本项目冲突。

Query 1, stage: `retrieval`.

```json
{
  "query": {
    "project_id": "BuildPilot",
    "subject": "project",
    "predicate": "region",
    "as_of": "2026-01-12T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "insufficient_evidence",
    "value": null,
    "event_ids": [
      "B16",
      "B17"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "eu-west-1",
    "evidence": [
      {
        "event_id": "B16",
        "project_id": "BuildPilot",
        "subject": "project",
        "predicate": "region",
        "value": "eu-west-1",
        "event_type": "declare",
        "observed_at": "2026-01-12T00:00:00Z",
        "effective_at": "2026-01-12T00:00:00Z",
        "source_id": "build-session-12",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "B16"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [],
  "missing_candidate_event_ids": [
    "B17"
  ],
  "leaked_event_ids": []
}
```

Query 2, stage: `provenance`.

```json
{
  "query": {
    "project_id": "ShopLedger",
    "subject": "project",
    "predicate": "region",
    "as_of": "2026-01-20T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "ap-east-1",
    "event_ids": [
      "S15",
      "S16"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "ap-east-1",
    "evidence": [
      {
        "event_id": "S16",
        "project_id": "ShopLedger",
        "subject": "project",
        "predicate": "region",
        "value": "ap-east-1",
        "event_type": "declare",
        "observed_at": "2026-01-13T00:00:00Z",
        "effective_at": "2026-01-12T00:00:00Z",
        "source_id": "shop-session-11",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "S15",
      "S16"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```


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
