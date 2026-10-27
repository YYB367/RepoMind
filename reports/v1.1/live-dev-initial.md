# 阶段目标：V1.1：分别验证有来源的事实提取、人工事件检索和端到端记忆回答

验证状态：`live_pipeline_measured`。真实提取与独立 Embedding 流水线已测量；完整发布仍需外部核心回归与独立保留集验收。

## 指标

| 阶段 / 指标 | 结果 | 分子 / 分母 |
|---|---:|---|
| 提取 Precision（完整事实） | 100.00% | 12 / 12 预测事实 |
| 提取 Recall（完整事实） | 92.31% | 12 / 13 标准事实 |
| 提取案例全对 | 91.67% | 11 / 12 案例 |
| 人工事件检索 Recall@3 | 100.00% | 14 / 14 有标准事实键的查询 |
| 人工事件 Top1 键命中 | 100.00% | 14 / 14 有标准事实键的查询 |
| 人工事件最终答案全对 | 87.50% | 14 / 16 查询 |
| 端到端最终答案全对 | 81.25% | 13 / 16 查询 |
| 端到端未知信息处理 | 33.33% | 1 / 3 预期 unknown 查询 |
| 原文引用与来源合法性（各阶段累计） | 100.00% | 104 / 104 检查 |
| 跨项目串用 | 0 | 含串用的查询数 |
| 全用例严格通过 | False | 每个提取案例 + 两条查询路径均全对 |
| 数值发布门槛 | True | 外部 pytest 与真实服务验证须另验 |
| 运行耗时 | 34.805251s | 含提取、导入、索引、查询和评分；不含报告写入 |

## 预先固定的门槛

```json
{
  "extraction_precision_min": 0.9,
  "extraction_recall_min": 0.85,
  "gold_retrieval_recall_at_3_min": 0.9,
  "end_to_end_accuracy_min": 0.8,
  "source_validity_required": 1.0,
  "project_leakage_max": 0
}
```

## 失败案例

### extraction / dev-07

```json
{
  "stage": "extraction",
  "case_id": "dev-07",
  "details": {
    "case_id": "dev-07",
    "passed": false,
    "error": "ValueError: provider extraction JSON violates the candidate schema",
    "source": {
      "project_id": "MarketMesh",
      "source_id": "source-dev-07",
      "observed_at": "2026-03-15T16:00:00Z",
      "text": "补记 MarketMesh：我们已在 2026-03-10T00:00:00Z 完成 database 从 SQLite 到 PostgreSQL 的迁移。"
    },
    "expected_count": 1,
    "predicted_count": 0,
    "matched_count": 0,
    "precision": null,
    "recall": 0.0,
    "missing_facts": [
      {
        "project_id": "MarketMesh",
        "source_id": "source-dev-07",
        "observed_at": "2026-03-15T16:00:00+00:00",
        "subject": "project",
        "predicate": "database",
        "value": "PostgreSQL",
        "event_type": "complete",
        "effective_at": "2026-03-10T00:00:00+00:00",
        "supersedes_event_id": null
      }
    ],
    "extra_facts": [],
    "quote_valid": 0,
    "quote_total": 0,
    "quote_checks": [],
    "actual_events": []
  }
}
```

### retrieval / dev-05

```json
{
  "stage": "retrieval",
  "case_id": "dev-05",
  "query_index": 1,
  "details": {
    "passed": false,
    "failure_stage": "retrieval",
    "error": null,
    "query": {
      "project_id": "ProjectOrion",
      "text": "ProjectOrion 的 cache 使用 Redis 吗？",
      "as_of": "2026-05-01T23:59:59.999999Z",
      "known_at": null,
      "expected_key": null,
      "expected_status": "unknown",
      "expected_value": null,
      "expected_source_ids": []
    },
    "rank": null,
    "recalled_at_3": false,
    "top1_correct": false,
    "answer_correct": false,
    "sources_correct": false,
    "actual_status": "ok",
    "actual_value": "PostgreSQL",
    "actual_source_ids": [
      "source-dev-02"
    ],
    "citation_valid": 3,
    "citation_total": 3,
    "citation_checks": [
      {
        "event_id": "synthetic-dev-02-1",
        "source_id": "source-dev-02",
        "valid": true,
        "problems": []
      },
      {
        "event_id": "orion-lang-0",
        "source_id": "seed-orion-jan",
        "valid": true,
        "problems": []
      },
      {
        "event_id": "synthetic-dev-03-1",
        "source_id": "source-dev-03",
        "valid": true,
        "problems": []
      }
    ],
    "project_leakage": false,
    "leaked_event_ids": [],
    "schema_issues": [],
    "response": {
      "project_id": "ProjectOrion",
      "query": "ProjectOrion 的 cache 使用 Redis 吗？",
      "mode": "hybrid",
      "as_of": "2026-05-01T23:59:59.999999+00:00",
      "known_at": null,
      "top_k": 3,
      "min_cosine": 0.2,
      "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
      "indexed_documents": 5,
      "hits": [
        {
          "subject": "project",
          "predicate": "database",
          "score": 0.01639344262295082,
          "lexical_score": 0.0,
          "semantic_score": 0.46213814402155445,
          "result": {
            "status": "ok",
            "value": "PostgreSQL",
            "evidence": [
              {
                "event_id": "synthetic-dev-02-1",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "database",
                "value": "PostgreSQL",
                "event_type": "complete",
                "observed_at": "2026-04-05T10:00:00Z",
                "effective_at": "2026-04-01T00:00:00Z",
                "source_id": "source-dev-02",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "orion-db-0",
              "synthetic-dev-01-1",
              "synthetic-dev-01-2",
              "synthetic-dev-02-1"
            ],
            "plan_event_ids": [
              "synthetic-dev-01-2"
            ]
          }
        },
        {
          "subject": "project",
          "predicate": "language",
          "score": 0.016129032258064516,
          "lexical_score": 0.0,
          "semantic_score": 0.4484993582733666,
          "result": {
            "status": "ok",
            "value": "Python 3.12",
            "evidence": [
              {
                "event_id": "orion-lang-0",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "language",
                "value": "Python 3.12",
                "event_type": "declare",
                "observed_at": "2026-01-01T00:00:00Z",
                "effective_at": "2026-01-01T00:00:00Z",
                "source_id": "seed-orion-jan",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "orion-lang-0",
              "synthetic-dev-04-1"
            ],
            "plan_event_ids": [
              "synthetic-dev-04-1"
            ]
          }
        },
        {
          "subject": "project",
          "predicate": "framework",
          "score": 0.015873015873015872,
          "lexical_score": 0.0,
          "semantic_score": 0.4440544308039789,
          "result": {
            "status": "ok",
            "value": "FastAPI",
            "evidence": [
              {
                "event_id": "synthetic-dev-03-1",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "framework",
                "value": "FastAPI",
                "event_type": "correct",
                "observed_at": "2026-05-01T08:00:00Z",
                "effective_at": "2026-01-01T00:00:00Z",
                "source_id": "source-dev-03",
                "supersedes_event_id": "orion-framework-0"
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "orion-framework-0",
              "synthetic-dev-03-1"
            ],
            "plan_event_ids": []
          }
        }
      ]
    }
  }
}
```

### end_to_end / dev-05

```json
{
  "stage": "end_to_end",
  "case_id": "dev-05",
  "query_index": 1,
  "details": {
    "passed": false,
    "failure_stage": "retrieval",
    "error": null,
    "query": {
      "project_id": "ProjectOrion",
      "text": "ProjectOrion 的 cache 使用 Redis 吗？",
      "as_of": "2026-05-01T23:59:59.999999Z",
      "known_at": null,
      "expected_key": null,
      "expected_status": "unknown",
      "expected_value": null,
      "expected_source_ids": []
    },
    "rank": null,
    "recalled_at_3": false,
    "top1_correct": false,
    "answer_correct": false,
    "sources_correct": false,
    "actual_status": "ok",
    "actual_value": "PostgreSQL",
    "actual_source_ids": [
      "source-dev-02"
    ],
    "citation_valid": 3,
    "citation_total": 3,
    "citation_checks": [
      {
        "event_id": "nl-ac36c73799fd60892c83311fe4dd948b",
        "source_id": "source-dev-02",
        "valid": true,
        "problems": []
      },
      {
        "event_id": "nl-5e7687767ba619d7c263abc71d6790eb",
        "source_id": "source-dev-03",
        "valid": true,
        "problems": []
      },
      {
        "event_id": "orion-lang-0",
        "source_id": "seed-orion-jan",
        "valid": true,
        "problems": []
      }
    ],
    "project_leakage": false,
    "leaked_event_ids": [],
    "schema_issues": [],
    "response": {
      "project_id": "ProjectOrion",
      "query": "ProjectOrion 的 cache 使用 Redis 吗？",
      "mode": "hybrid",
      "as_of": "2026-05-01T23:59:59.999999+00:00",
      "known_at": null,
      "top_k": 3,
      "min_cosine": 0.2,
      "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
      "indexed_documents": 5,
      "hits": [
        {
          "subject": "project",
          "predicate": "database",
          "score": 0.01639344262295082,
          "lexical_score": 0.0,
          "semantic_score": 0.4639361722310047,
          "result": {
            "status": "ok",
            "value": "PostgreSQL",
            "evidence": [
              {
                "event_id": "nl-ac36c73799fd60892c83311fe4dd948b",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "database",
                "value": "PostgreSQL",
                "event_type": "complete",
                "observed_at": "2026-04-05T10:00:00Z",
                "effective_at": "2026-04-01T00:00:00Z",
                "source_id": "source-dev-02",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "nl-416ff072f400e360da947483a5db61fa",
              "nl-621b84f5bcbe2c6b73c6da06d5b31f8a",
              "nl-ac36c73799fd60892c83311fe4dd948b",
              "orion-db-0"
            ],
            "plan_event_ids": [
              "nl-621b84f5bcbe2c6b73c6da06d5b31f8a"
            ]
          }
        },
        {
          "subject": "project",
          "predicate": "framework",
          "score": 0.016129032258064516,
          "lexical_score": 0.0,
          "semantic_score": 0.4553201987461924,
          "result": {
            "status": "ok",
            "value": "FastAPI",
            "evidence": [
              {
                "event_id": "nl-5e7687767ba619d7c263abc71d6790eb",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "framework",
                "value": "FastAPI",
                "event_type": "correct",
                "observed_at": "2026-05-01T08:00:00Z",
                "effective_at": "2026-01-01T00:00:00Z",
                "source_id": "source-dev-03",
                "supersedes_event_id": "orion-framework-0"
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "nl-5e7687767ba619d7c263abc71d6790eb",
              "orion-framework-0"
            ],
            "plan_event_ids": []
          }
        },
        {
          "subject": "project",
          "predicate": "language",
          "score": 0.015873015873015872,
          "lexical_score": 0.0,
          "semantic_score": 0.45235624213097164,
          "result": {
            "status": "ok",
            "value": "Python 3.12",
            "evidence": [
              {
                "event_id": "orion-lang-0",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "language",
                "value": "Python 3.12",
                "event_type": "declare",
                "observed_at": "2026-01-01T00:00:00Z",
                "effective_at": "2026-01-01T00:00:00Z",
                "source_id": "seed-orion-jan",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "nl-659007ef44e8f9b7d92e06bb0405c5cc",
              "orion-lang-0"
            ],
            "plan_event_ids": [
              "nl-659007ef44e8f9b7d92e06bb0405c5cc"
            ]
          }
        }
      ]
    },
    "extraction_ledger_differs": false
  }
}
```

### end_to_end / dev-07

```json
{
  "stage": "end_to_end",
  "case_id": "dev-07",
  "query_index": 1,
  "details": {
    "passed": false,
    "failure_stage": "extraction",
    "error": null,
    "query": {
      "project_id": "MarketMesh",
      "text": "MarketMesh 使用哪个 database？",
      "as_of": "2026-03-12T23:59:59.999999Z",
      "known_at": null,
      "expected_key": [
        "project",
        "database"
      ],
      "expected_status": "ok",
      "expected_value": "PostgreSQL",
      "expected_source_ids": [
        "source-dev-07"
      ]
    },
    "rank": 1,
    "recalled_at_3": true,
    "top1_correct": true,
    "answer_correct": false,
    "sources_correct": false,
    "actual_status": "ok",
    "actual_value": "SQLite",
    "actual_source_ids": [
      "seed-market-jan"
    ],
    "citation_valid": 2,
    "citation_total": 2,
    "citation_checks": [
      {
        "event_id": "market-db-0",
        "source_id": "seed-market-jan",
        "valid": true,
        "problems": []
      },
      {
        "event_id": "market-framework-0",
        "source_id": "seed-market-jan",
        "valid": true,
        "problems": []
      }
    ],
    "project_leakage": false,
    "leaked_event_ids": [],
    "schema_issues": [],
    "response": {
      "project_id": "MarketMesh",
      "query": "MarketMesh 使用哪个 database？",
      "mode": "hybrid",
      "as_of": "2026-03-12T23:59:59.999999+00:00",
      "known_at": null,
      "top_k": 3,
      "min_cosine": 0.2,
      "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
      "indexed_documents": 5,
      "hits": [
        {
          "subject": "project",
          "predicate": "database",
          "score": 0.03278688524590164,
          "lexical_score": 0.16903085094570328,
          "semantic_score": 0.4432262510090408,
          "result": {
            "status": "ok",
            "value": "SQLite",
            "evidence": [
              {
                "event_id": "market-db-0",
                "project_id": "MarketMesh",
                "subject": "project",
                "predicate": "database",
                "value": "SQLite",
                "event_type": "declare",
                "observed_at": "2026-01-03T00:00:00Z",
                "effective_at": "2026-01-03T00:00:00Z",
                "source_id": "seed-market-jan",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "market-db-0"
            ],
            "plan_event_ids": []
          }
        },
        {
          "subject": "project",
          "predicate": "search_engine",
          "score": 0.016129032258064516,
          "lexical_score": 0.0,
          "semantic_score": 0.3873375264425613,
          "result": {
            "status": "unknown",
            "value": null,
            "evidence": [],
            "reason": "no_effective_fact",
            "considered_event_ids": [
              "nl-0c8ddc0cc8539b257549bdf0335e0f5e"
            ],
            "plan_event_ids": []
          }
        },
        {
          "subject": "project",
          "predicate": "framework",
          "score": 0.015873015873015872,
          "lexical_score": 0.0,
          "semantic_score": 0.3013863896897642,
          "result": {
            "status": "ok",
            "value": "Express",
            "evidence": [
              {
                "event_id": "market-framework-0",
                "project_id": "MarketMesh",
                "subject": "project",
                "predicate": "framework",
                "value": "Express",
                "event_type": "declare",
                "observed_at": "2026-01-03T00:00:00Z",
                "effective_at": "2026-01-03T00:00:00Z",
                "source_id": "seed-market-jan",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "market-framework-0",
              "nl-6940ac934fdf313b2e409f9326f344cd",
              "nl-bce47542d7b95da6ad92cc7b7d5b1352"
            ],
            "plan_event_ids": []
          }
        }
      ]
    },
    "extraction_ledger_differs": true
  }
}
```

### retrieval / dev-12

```json
{
  "stage": "retrieval",
  "case_id": "dev-12",
  "query_index": 2,
  "details": {
    "passed": false,
    "failure_stage": "retrieval",
    "error": null,
    "query": {
      "project_id": "ProjectOrion",
      "text": "ProjectOrion 的 search_engine 是什么？",
      "as_of": "2026-05-02T23:59:59.999999Z",
      "known_at": null,
      "expected_key": null,
      "expected_status": "unknown",
      "expected_value": null,
      "expected_source_ids": []
    },
    "rank": null,
    "recalled_at_3": false,
    "top1_correct": false,
    "answer_correct": false,
    "sources_correct": false,
    "actual_status": "ok",
    "actual_value": "Python 3.12",
    "actual_source_ids": [
      "seed-orion-jan"
    ],
    "citation_valid": 3,
    "citation_total": 3,
    "citation_checks": [
      {
        "event_id": "orion-lang-0",
        "source_id": "seed-orion-jan",
        "valid": true,
        "problems": []
      },
      {
        "event_id": "synthetic-dev-02-1",
        "source_id": "source-dev-02",
        "valid": true,
        "problems": []
      },
      {
        "event_id": "synthetic-dev-03-1",
        "source_id": "source-dev-03",
        "valid": true,
        "problems": []
      }
    ],
    "project_leakage": false,
    "leaked_event_ids": [],
    "schema_issues": [],
    "response": {
      "project_id": "ProjectOrion",
      "query": "ProjectOrion 的 search_engine 是什么？",
      "mode": "hybrid",
      "as_of": "2026-05-02T23:59:59.999999+00:00",
      "known_at": null,
      "top_k": 3,
      "min_cosine": 0.2,
      "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
      "indexed_documents": 5,
      "hits": [
        {
          "subject": "project",
          "predicate": "language",
          "score": 0.01639344262295082,
          "lexical_score": 0.0,
          "semantic_score": 0.5098813909728617,
          "result": {
            "status": "ok",
            "value": "Python 3.12",
            "evidence": [
              {
                "event_id": "orion-lang-0",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "language",
                "value": "Python 3.12",
                "event_type": "declare",
                "observed_at": "2026-01-01T00:00:00Z",
                "effective_at": "2026-01-01T00:00:00Z",
                "source_id": "seed-orion-jan",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "orion-lang-0",
              "synthetic-dev-04-1"
            ],
            "plan_event_ids": [
              "synthetic-dev-04-1"
            ]
          }
        },
        {
          "subject": "project",
          "predicate": "database",
          "score": 0.016129032258064516,
          "lexical_score": 0.0,
          "semantic_score": 0.47786100481964827,
          "result": {
            "status": "ok",
            "value": "PostgreSQL",
            "evidence": [
              {
                "event_id": "synthetic-dev-02-1",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "database",
                "value": "PostgreSQL",
                "event_type": "complete",
                "observed_at": "2026-04-05T10:00:00Z",
                "effective_at": "2026-04-01T00:00:00Z",
                "source_id": "source-dev-02",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "orion-db-0",
              "synthetic-dev-01-1",
              "synthetic-dev-01-2",
              "synthetic-dev-02-1"
            ],
            "plan_event_ids": [
              "synthetic-dev-01-2"
            ]
          }
        },
        {
          "subject": "project",
          "predicate": "framework",
          "score": 0.015873015873015872,
          "lexical_score": 0.0,
          "semantic_score": 0.46802897763331736,
          "result": {
            "status": "ok",
            "value": "FastAPI",
            "evidence": [
              {
                "event_id": "synthetic-dev-03-1",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "framework",
                "value": "FastAPI",
                "event_type": "correct",
                "observed_at": "2026-05-01T08:00:00Z",
                "effective_at": "2026-01-01T00:00:00Z",
                "source_id": "source-dev-03",
                "supersedes_event_id": "orion-framework-0"
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "orion-framework-0",
              "synthetic-dev-03-1"
            ],
            "plan_event_ids": []
          }
        }
      ]
    }
  }
}
```

### end_to_end / dev-12

```json
{
  "stage": "end_to_end",
  "case_id": "dev-12",
  "query_index": 2,
  "details": {
    "passed": false,
    "failure_stage": "retrieval",
    "error": null,
    "query": {
      "project_id": "ProjectOrion",
      "text": "ProjectOrion 的 search_engine 是什么？",
      "as_of": "2026-05-02T23:59:59.999999Z",
      "known_at": null,
      "expected_key": null,
      "expected_status": "unknown",
      "expected_value": null,
      "expected_source_ids": []
    },
    "rank": null,
    "recalled_at_3": false,
    "top1_correct": false,
    "answer_correct": false,
    "sources_correct": false,
    "actual_status": "ok",
    "actual_value": "Python 3.12",
    "actual_source_ids": [
      "seed-orion-jan"
    ],
    "citation_valid": 3,
    "citation_total": 3,
    "citation_checks": [
      {
        "event_id": "orion-lang-0",
        "source_id": "seed-orion-jan",
        "valid": true,
        "problems": []
      },
      {
        "event_id": "nl-ac36c73799fd60892c83311fe4dd948b",
        "source_id": "source-dev-02",
        "valid": true,
        "problems": []
      },
      {
        "event_id": "nl-5e7687767ba619d7c263abc71d6790eb",
        "source_id": "source-dev-03",
        "valid": true,
        "problems": []
      }
    ],
    "project_leakage": false,
    "leaked_event_ids": [],
    "schema_issues": [],
    "response": {
      "project_id": "ProjectOrion",
      "query": "ProjectOrion 的 search_engine 是什么？",
      "mode": "hybrid",
      "as_of": "2026-05-02T23:59:59.999999+00:00",
      "known_at": null,
      "top_k": 3,
      "min_cosine": 0.2,
      "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
      "indexed_documents": 5,
      "hits": [
        {
          "subject": "project",
          "predicate": "language",
          "score": 0.01639344262295082,
          "lexical_score": 0.0,
          "semantic_score": 0.5195833443844317,
          "result": {
            "status": "ok",
            "value": "Python 3.12",
            "evidence": [
              {
                "event_id": "orion-lang-0",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "language",
                "value": "Python 3.12",
                "event_type": "declare",
                "observed_at": "2026-01-01T00:00:00Z",
                "effective_at": "2026-01-01T00:00:00Z",
                "source_id": "seed-orion-jan",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "nl-659007ef44e8f9b7d92e06bb0405c5cc",
              "orion-lang-0"
            ],
            "plan_event_ids": [
              "nl-659007ef44e8f9b7d92e06bb0405c5cc"
            ]
          }
        },
        {
          "subject": "project",
          "predicate": "database",
          "score": 0.016129032258064516,
          "lexical_score": 0.0,
          "semantic_score": 0.4852168806417579,
          "result": {
            "status": "ok",
            "value": "PostgreSQL",
            "evidence": [
              {
                "event_id": "nl-ac36c73799fd60892c83311fe4dd948b",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "database",
                "value": "PostgreSQL",
                "event_type": "complete",
                "observed_at": "2026-04-05T10:00:00Z",
                "effective_at": "2026-04-01T00:00:00Z",
                "source_id": "source-dev-02",
                "supersedes_event_id": null
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "nl-416ff072f400e360da947483a5db61fa",
              "nl-621b84f5bcbe2c6b73c6da06d5b31f8a",
              "nl-ac36c73799fd60892c83311fe4dd948b",
              "orion-db-0"
            ],
            "plan_event_ids": [
              "nl-621b84f5bcbe2c6b73c6da06d5b31f8a"
            ]
          }
        },
        {
          "subject": "project",
          "predicate": "framework",
          "score": 0.015873015873015872,
          "lexical_score": 0.0,
          "semantic_score": 0.47250401713460644,
          "result": {
            "status": "ok",
            "value": "FastAPI",
            "evidence": [
              {
                "event_id": "nl-5e7687767ba619d7c263abc71d6790eb",
                "project_id": "ProjectOrion",
                "subject": "project",
                "predicate": "framework",
                "value": "FastAPI",
                "event_type": "correct",
                "observed_at": "2026-05-01T08:00:00Z",
                "effective_at": "2026-01-01T00:00:00Z",
                "source_id": "source-dev-03",
                "supersedes_event_id": "orion-framework-0"
              }
            ],
            "reason": "latest_effective_fact",
            "considered_event_ids": [
              "nl-5e7687767ba619d7c263abc71d6790eb",
              "orion-framework-0"
            ],
            "plan_event_ids": []
          }
        }
      ]
    },
    "extraction_ledger_differs": false
  }
}
```


## 配置与复现证据

```json
{
  "inputs": {
    "seeds": {
      "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.1\\seed-events.jsonl",
      "sha256": "e783d9e1d58594be22f696b134357cb14c992c7231e2146f6d5eb7b9504c1009"
    },
    "gold_events": {
      "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.1\\gold-events.jsonl",
      "sha256": "f9e79374996530b0bfd0184036649cf5518533d21f108dac7381a6370607ed34"
    },
    "dataset": {
      "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.1\\dev\\cases.jsonl",
      "sha256": "4a5edee69ab281d8319f309b8039cb8b98e41f6af4cd28dfa19fe6eddd38ff4d"
    }
  },
  "dataset_split": "dev",
  "python_version": "3.12.14",
  "repomind_source_version": "1.1.0rc1",
  "repomind_installed_version": "1.1.0rc1",
  "pydantic_version": "2.14.1",
  "sqlite_version": "3.53.1",
  "extraction_provider": {
    "name": "deepseek:chat=deepseek-flash;embedding=unset;format=json_object",
    "fingerprint": "openai-compatible-83311ef5799a5777bac725539a1eb5747f747343282ef4efaf26301fe1e2e238",
    "request_count": 12,
    "usage": {
      "prompt_tokens": 15307,
      "completion_tokens": 1187,
      "total_tokens": 16494
    },
    "base_url": "https://api.deepseek.com",
    "chat_model": "deepseek-flash",
    "embedding_model": null,
    "api_style": "deepseek",
    "chat_format": "json_object",
    "timeout_seconds": 60.0,
    "max_response_bytes": 1000000,
    "max_request_bytes": 2000000,
    "max_completion_tokens": 2048,
    "embedding_dimensions": null
  },
  "embedding_provider": {
    "name": "openai:chat=unset;embedding=qwen3.7-text-embedding-flash;format=json_schema",
    "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
    "request_count": 42,
    "usage": {
      "prompt_tokens": 2037,
      "total_tokens": 2037
    },
    "base_url": "https://maas.qianwenaiapi.com/compatible-mode/v1",
    "chat_model": null,
    "embedding_model": "qwen3.7-text-embedding-flash",
    "api_style": "openai",
    "chat_format": null,
    "timeout_seconds": 60.0,
    "max_response_bytes": 1000000,
    "max_request_bytes": 2000000,
    "max_completion_tokens": 2048,
    "embedding_dimensions": 1024
  },
  "search_mode": "hybrid",
  "top_k": 3,
  "min_cosine": 0.2,
  "ingestion_policy": "ingest every split source into seeds-only actual ledger before any query; gold retrieval ledger is separate",
  "extraction_scoring": "whole fact set including trusted source/project/observation, effective time, type, correction target; exact source substring independently audited",
  "query_scoring": "ranked key + top1 status/value + exact source-ID set + every cited ledger event valid",
  "zero_denominator_policy": "null/N/A; lack of positive samples does not satisfy a numeric release gate",
  "release_thresholds": {
    "extraction_precision_min": 0.9,
    "extraction_recall_min": 0.85,
    "gold_retrieval_recall_at_3_min": 0.9,
    "end_to_end_accuracy_min": 0.8,
    "source_validity_required": 1.0,
    "project_leakage_max": 0
  },
  "semantic_claim_boundary": "recorded vectors and lexical search cannot establish real embedding quality"
}
```

## 边界

- 录制提取响应和录制向量是人工测试替身，不代表真实语言理解或语义检索质量。真实 chat 配合 lexical 也不能证明 Embedding 效果。
- 引文只要求是原文中的精确片段，不要求与单一标准引文逐字相同。片段存在不证明模型的语义解释必然正确。
- 检索路径使用人工事件；端到端路径仅从 seeds 和本次真实提取结果构建，不复制标准事件。所有案例先导入完毕，再按查询时间切片评分。
- 来源合法性只验证账本一致性、项目与事实键、时间和原文片段，不认证外部来源真实性。
- 微平均提取 Precision/Recall 比较完整事实集合（含类型、时间和纠错目标）；所有零分母指标显示 N/A。
- all_passed 比数值门槛严格。release_gate_passed 只报告既定数值门槛，不能替代外部核心回归或独立保留集和真实模型验收。
- 这批合成样本很小；时间戳、环境路径、耗时和实际模型响应可变，不构成生产可靠性保证。
