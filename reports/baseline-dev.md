# RepoMind V1 evaluation report

Strategy: `latest_observation_baseline`. Generated UTC: `2026-10-26T11:08:45.316864+00:00`.

A question passes only when every structured query has the correct status, value, exact evidence set, and valid citations.

| Metric | Result | Denominator / unit |
|---|---:|---|
| Strict question accuracy | 68.75% | 22 / 32 questions |
| Status/value question accuracy | 78.12% | 32 questions |
| Unknown-information handling | 80.00% | 4 / 5 expected-unknown queries |
| Refusal correctness (unknown + conflict) | 66.67% | 4 / 6 expected-refusal queries |
| Cross-project leakage | 0 | queries with an out-of-project candidate/citation |
| Source citation validity | 87.18% | 34 / 39 citations |
| Exact expected evidence | 76.74% | 33 / 43 queries |
| Runtime | 0.044557 | seconds, validation + temporary DB import + queries + scoring; report I/O excluded |

## Categories

| Category | Passed / total | Strict accuracy |
|---|---:|---:|
| basic | 6 / 6 | 100.00% |
| cross_session | 4 / 6 | 66.67% |
| isolation | 4 / 5 | 80.00% |
| state | 2 / 5 | 40.00% |
| temporal | 2 / 5 | 40.00% |
| unknown | 4 / 5 | 80.00% |

## Failures

### D-T02: 迁移计划没有改变实际数据库。

Query 1, stage: `provenance`.

```json
{
  "query": {
    "project_id": "CampusRecruit",
    "subject": "project",
    "predicate": "database",
    "as_of": "2026-03-20T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "MySQL",
    "event_ids": [
      "C01"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "PostgreSQL",
    "evidence": [
      {
        "event_id": "C05",
        "project_id": "CampusRecruit",
        "subject": "project",
        "predicate": "database",
        "value": "PostgreSQL",
        "event_type": "plan",
        "observed_at": "2026-03-01T00:00:00Z",
        "effective_at": "2026-04-01T00:00:00Z",
        "source_id": "campus-session-03",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "C01",
      "C05"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [
    {
      "event_id": "C05",
      "reason": "citation is not effective at as_of; plan cannot support an implemented fact"
    }
  ],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### D-T04: 账本迁移完成前使用 SQLite。

Query 1, stage: `provenance`.

```json
{
  "query": {
    "project_id": "ShopLedger",
    "subject": "project",
    "predicate": "database",
    "as_of": "2026-02-20T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "SQLite",
    "event_ids": [
      "S01"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "PostgreSQL",
    "evidence": [
      {
        "event_id": "S05",
        "project_id": "ShopLedger",
        "subject": "project",
        "predicate": "database",
        "value": "PostgreSQL",
        "event_type": "plan",
        "observed_at": "2026-02-01T00:00:00Z",
        "effective_at": "2026-03-01T00:00:00Z",
        "source_id": "shop-session-03",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "S01",
      "S05"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [
    {
      "event_id": "S05",
      "reason": "citation is not effective at as_of; plan cannot support an implemented fact"
    }
  ],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### D-T05: 当时尚未观察到迟到的完成记录。

Query 1, stage: `provenance`.

```json
{
  "query": {
    "project_id": "ShopLedger",
    "subject": "project",
    "predicate": "database",
    "as_of": "2026-03-01T23:59:59.999999Z",
    "known_at": "2026-03-01T23:59:59.999999Z"
  },
  "expected": {
    "status": "ok",
    "value": "SQLite",
    "event_ids": [
      "S01"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "PostgreSQL",
    "evidence": [
      {
        "event_id": "S05",
        "project_id": "ShopLedger",
        "subject": "project",
        "predicate": "database",
        "value": "PostgreSQL",
        "event_type": "plan",
        "observed_at": "2026-02-01T00:00:00Z",
        "effective_at": "2026-03-01T00:00:00Z",
        "source_id": "shop-session-03",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "S01",
      "S05"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [
    {
      "event_id": "S05",
      "reason": "plan cannot support an implemented fact"
    }
  ],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### D-S01: 用当前知识重建被纠正的历史配置。

Query 1, stage: `retrieval`.

```json
{
  "query": {
    "project_id": "CampusRecruit",
    "subject": "project",
    "predicate": "runtime_memory",
    "as_of": "2026-01-20T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "16GB",
    "event_ids": [
      "C09"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "8GB",
    "evidence": [
      {
        "event_id": "C08",
        "project_id": "CampusRecruit",
        "subject": "project",
        "predicate": "runtime_memory",
        "value": "8GB",
        "event_type": "declare",
        "observed_at": "2026-01-10T00:00:00Z",
        "effective_at": "2026-01-10T00:00:00Z",
        "source_id": "campus-session-06",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "C08"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [],
  "missing_candidate_event_ids": [
    "C09"
  ],
  "leaked_event_ids": []
}
```

### D-S04: 同刻时区相互矛盾，拒绝确定答案。

Query 1, stage: `resolution`.

```json
{
  "query": {
    "project_id": "ShopLedger",
    "subject": "project",
    "predicate": "timezone",
    "as_of": "2026-02-01T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "insufficient_evidence",
    "value": null,
    "event_ids": [
      "S13",
      "S14"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "Asia/Shanghai",
    "evidence": [
      {
        "event_id": "S14",
        "project_id": "ShopLedger",
        "subject": "project",
        "predicate": "timezone",
        "value": "Asia/Shanghai",
        "event_type": "declare",
        "observed_at": "2026-01-09T00:00:00Z",
        "effective_at": "2026-01-08T00:00:00Z",
        "source_id": "shop-session-09",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "S13",
      "S14"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### D-S05: 纠错只替代指定分支，同值证据联合返回。

Query 1, stage: `provenance`.

```json
{
  "query": {
    "project_id": "CampusRecruit",
    "subject": "project",
    "predicate": "queue",
    "as_of": "2026-03-20T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "RabbitMQ",
    "event_ids": [
      "C14",
      "C16"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "RabbitMQ",
    "evidence": [
      {
        "event_id": "C16",
        "project_id": "CampusRecruit",
        "subject": "project",
        "predicate": "queue",
        "value": "RabbitMQ",
        "event_type": "correct",
        "observed_at": "2026-03-12T00:00:00Z",
        "effective_at": "2026-03-01T00:00:00Z",
        "source_id": "campus-session-12",
        "supersedes_event_id": "C15"
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "C14",
      "C15",
      "C16"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### D-C05: 关联缓存完成与队列纠错会话。

Query 2, stage: `provenance`.

```json
{
  "query": {
    "project_id": "CampusRecruit",
    "subject": "project",
    "predicate": "queue",
    "as_of": "2026-04-16T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "RabbitMQ",
    "event_ids": [
      "C14",
      "C16"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "RabbitMQ",
    "evidence": [
      {
        "event_id": "C16",
        "project_id": "CampusRecruit",
        "subject": "project",
        "predicate": "queue",
        "value": "RabbitMQ",
        "event_type": "correct",
        "observed_at": "2026-03-12T00:00:00Z",
        "effective_at": "2026-03-01T00:00:00Z",
        "source_id": "campus-session-12",
        "supersedes_event_id": "C15"
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "C14",
      "C15",
      "C16"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### D-C06: 联合区域双来源佐证与接口记录。

Query 1, stage: `provenance`.

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

### D-I02: 分析模块不能覆盖项目默认数据库。

Query 2, stage: `provenance`.

```json
{
  "query": {
    "project_id": "ShopLedger",
    "subject": "project",
    "predicate": "database",
    "as_of": "2026-02-01T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "ok",
    "value": "SQLite",
    "event_ids": [
      "S01"
    ]
  },
  "actual": {
    "status": "ok",
    "value": "PostgreSQL",
    "evidence": [
      {
        "event_id": "S05",
        "project_id": "ShopLedger",
        "subject": "project",
        "predicate": "database",
        "value": "PostgreSQL",
        "event_type": "plan",
        "observed_at": "2026-02-01T00:00:00Z",
        "effective_at": "2026-03-01T00:00:00Z",
        "source_id": "shop-session-03",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "S01",
      "S05"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [
    {
      "event_id": "S05",
      "reason": "citation is not effective at as_of; plan cannot support an implemented fact"
    }
  ],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```

### D-U02: 只有计划，没有队列实际状态证据。

Query 1, stage: `provenance`.

```json
{
  "query": {
    "project_id": "ShopLedger",
    "subject": "project",
    "predicate": "queue",
    "as_of": "2026-03-10T23:59:59.999999Z",
    "known_at": null
  },
  "expected": {
    "status": "unknown",
    "value": null,
    "event_ids": []
  },
  "actual": {
    "status": "ok",
    "value": "Kafka",
    "evidence": [
      {
        "event_id": "S17",
        "project_id": "ShopLedger",
        "subject": "project",
        "predicate": "queue",
        "value": "Kafka",
        "event_type": "plan",
        "observed_at": "2026-02-04T00:00:00Z",
        "effective_at": "2026-03-04T00:00:00Z",
        "source_id": "shop-session-12",
        "supersedes_event_id": null
      }
    ],
    "reason": "baseline: latest observation; ignores event type/effective time",
    "considered_event_ids": [
      "S17"
    ],
    "plan_event_ids": []
  },
  "citation_issues": [
    {
      "event_id": "S17",
      "reason": "plan cannot support an implemented fact"
    }
  ],
  "missing_candidate_event_ids": [],
  "leaked_event_ids": []
}
```


## Configuration

```json
{
  "events_path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\fixtures\\conversations.jsonl",
  "dataset_path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\dev\\questions.jsonl",
  "events_sha256": "4542212c9842d1ba32a10fa492eed573db56bb77698d7bb68fb4ecd13e8bac69",
  "dataset_sha256": "7820c63c1891be167e61e55354a378d20e62568c057351528f27c63bfd080c8b",
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
