# 阶段目标：V1.2：建立可复现的检索对照、实际用量计量和可读回核验的 Langfuse 追踪/实验

运行 `recorded-dev-first`；模式 `recorded`。

受控检索比较：相同事实键文档/模型/项目和时间范围，共用 V1 resolver；Mem0 infer=False。

| 方案 | 严格正确 | Recall@3 | 引用合法 | 越界查询 | 实际 API 请求 | 费用估算 |
|---|---:|---:|---:|---:|---:|---|
| repomind_hybrid | 12/12 | 100.0% | 100.0% | 0 | 0 | 未知（not_measured_recorded_vectors） |
| no_memory | 2/12 | 0.0% | N/A | 0 | 0 | 未知（not_measured_recorded_vectors） |
| repomind_semantic | 12/12 | 100.0% | 100.0% | 0 | 0 | 未知（not_measured_recorded_vectors） |
| mem0 | 12/12 | 100.0% | 100.0% | 0 | 0 | 未知（not_measured_recorded_vectors） |

## 计量与结论边界

- search_and_resolution 包含检索和 V1 规则解析；不声称单独测得 resolver 耗时。索引、查询、评分、准备和报告写入分别计时。
- 延迟是单轮小样本描述，含 Mem0 本地 HTTP 桥开销。原始索引/热缓存次数见 JSON；不能外推吞吐量或生产可靠性。
- 无记忆组是负对照；工程完成标志不以它的准确率为门槛。各组实际失败案例全部保留。
- recorded 是理想排序测试替身，不能证明真实语义质量或节省费用；live 的 token 来自真实返回，费用只有显式价卡估算，不等于账单。
- 纯语义自研与 Mem0 是主要受控对照；混合检索额外使用词法信号。共享 resolver 意味着本结果不评测 Mem0 原生事实提取/冲突/时间处理。
- 本地 outbox 成功不等于云端保存；trace-sync 后仍需云端读回证据。Experiment 回放预计算输出，不重调模型。

## 运行配置

```json
{
  "version": "1.2.0rc1",
  "python": "3.12.14",
  "sdk_versions": {
    "pydantic": "2.14.1",
    "langfuse": "5.0.4",
    "mem0ai": "2.2.1",
    "qdrant-client": "1.20.0",
    "openai": "3.39.0"
  },
  "implementation_sha256": "dc175425d60166602456e655ed393897eb6faba957a4691ff2d9eb8a1592d836",
  "vector_mode": "recorded",
  "events": {
    "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.2\\events.jsonl",
    "sha256": "55b21fb5a6b5a0ec90dc84d3a48a6a7c1e89bc481a0f63e182b4ecdf2b55e018"
  },
  "dataset": {
    "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.2\\dev\\questions.jsonl",
    "sha256": "359f126b0963c42dc8d8c12cf9ee333938d6bab8361d38ab6b569d4678f2bc2f"
  },
  "vectors": {
    "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.2\\recorded-vectors.json",
    "sha256": "40b4a772a64a0558ed30d970fa3952ee036c69dc365a72c681b7655598f33e7b"
  },
  "manifest": {
    "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.2\\manifest.json",
    "sha256": "19937f893c3888fa7b45f3607d160f7323a53ece4de8de261f308e57ea490184"
  },
  "synthetic": true,
  "event_count": 30,
  "query_count": 12,
  "top_k": 3,
  "min_cosine": 0.55,
  "seed": 0,
  "provider_order": [
    "repomind_hybrid",
    "no_memory",
    "repomind_semantic",
    "mem0"
  ],
  "state_directory": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\work\\v12-runs\\recorded-dev-first",
  "price_card_sha256": null,
  "same_data_policy": "independent store + embedding client per arm; no gold passed to provider; no shared paid-call cache",
  "primary_comparison": [
    "repomind_semantic",
    "mem0"
  ],
  "resolver_timing": "included in search_and_resolution"
}
```

## 延迟与分类指标

```json
{
  "repomind_hybrid": {
    "timings": {
      "index": {
        "n": 12,
        "total_seconds": 0.052974200050812215,
        "p50_seconds": 0.0007192000048235059,
        "p95_seconds": 0.012607500015292317,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 0.009719099965877831,
        "p50_seconds": 0.0007924000092316419,
        "p95_seconds": 0.0011676999856717885,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.0030337000207509845,
        "p50_seconds": 0.00022429999080486596,
        "p95_seconds": 0.0005304999940562993,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.033308600017335266,
      "cold_index_requests": 4,
      "warm_index_requests": 8
    },
    "by_category": {
      "basic": {
        "total_queries": 2,
        "correct": 2,
        "accuracy": 1.0,
        "key_queries": 2,
        "recalled_at_3": 2,
        "recall_at_3": 1.0,
        "top1_key_correct": 2,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 3,
        "citation_total": 3,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 2,
        "source_set_correct_count": 2,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "isolation": {
        "total_queries": 1,
        "correct": 1,
        "accuracy": 1.0,
        "key_queries": 1,
        "recalled_at_3": 1,
        "recall_at_3": 1.0,
        "top1_key_correct": 1,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 2,
        "citation_total": 2,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 1,
        "source_set_correct_count": 1,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "state": {
        "total_queries": 4,
        "correct": 4,
        "accuracy": 1.0,
        "key_queries": 4,
        "recalled_at_3": 4,
        "recall_at_3": 1.0,
        "top1_key_correct": 4,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 5,
        "citation_total": 5,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 4,
        "source_set_correct_count": 4,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "temporal": {
        "total_queries": 3,
        "correct": 3,
        "accuracy": 1.0,
        "key_queries": 3,
        "recalled_at_3": 3,
        "recall_at_3": 1.0,
        "top1_key_correct": 3,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 6,
        "citation_total": 6,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 3,
        "source_set_correct_count": 3,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "unknown": {
        "total_queries": 2,
        "correct": 2,
        "accuracy": 1.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 2,
        "no_key_correct": 2,
        "no_key_rejection_rate": 1.0,
        "unknown_expected_count": 2,
        "unknown_correct": 2,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 2,
        "source_set_correct_count": 2,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      }
    }
  },
  "no_memory": {
    "timings": {
      "index": {
        "n": 12,
        "total_seconds": 7.379997987300158e-05,
        "p50_seconds": 4.0000013541430235e-06,
        "p95_seconds": 1.829999382607639e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 0.0004460999625734985,
        "p50_seconds": 3.160000778734684e-05,
        "p95_seconds": 6.209997809492052e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.00033779998193494976,
        "p50_seconds": 2.099998528137803e-05,
        "p95_seconds": 4.199999966658652e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.033014000015100464,
      "cold_index_requests": 0,
      "warm_index_requests": 0
    },
    "by_category": {
      "basic": {
        "total_queries": 2,
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 2,
        "recalled_at_3": 0,
        "recall_at_3": 0.0,
        "top1_key_correct": 0,
        "top1_key_accuracy": 0.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 0,
        "source_set_correct_count": 0,
        "failure_stage_counts": {
          "retrieval": 2,
          "resolution": 0,
          "provenance": 0
        }
      },
      "isolation": {
        "total_queries": 1,
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 1,
        "recalled_at_3": 0,
        "recall_at_3": 0.0,
        "top1_key_correct": 0,
        "top1_key_accuracy": 0.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 0,
        "source_set_correct_count": 0,
        "failure_stage_counts": {
          "retrieval": 1,
          "resolution": 0,
          "provenance": 0
        }
      },
      "state": {
        "total_queries": 4,
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 4,
        "recalled_at_3": 0,
        "recall_at_3": 0.0,
        "top1_key_correct": 0,
        "top1_key_accuracy": 0.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 0,
        "source_set_correct_count": 0,
        "failure_stage_counts": {
          "retrieval": 4,
          "resolution": 0,
          "provenance": 0
        }
      },
      "temporal": {
        "total_queries": 3,
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 3,
        "recalled_at_3": 0,
        "recall_at_3": 0.0,
        "top1_key_correct": 0,
        "top1_key_accuracy": 0.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 0,
        "source_set_correct_count": 0,
        "failure_stage_counts": {
          "retrieval": 3,
          "resolution": 0,
          "provenance": 0
        }
      },
      "unknown": {
        "total_queries": 2,
        "correct": 2,
        "accuracy": 1.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 2,
        "no_key_correct": 2,
        "no_key_rejection_rate": 1.0,
        "unknown_expected_count": 2,
        "unknown_correct": 2,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 2,
        "source_set_correct_count": 2,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      }
    }
  },
  "repomind_semantic": {
    "timings": {
      "index": {
        "n": 12,
        "total_seconds": 0.05162939999718219,
        "p50_seconds": 0.0007479000196326524,
        "p95_seconds": 0.012164199986727908,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 0.008317999978316948,
        "p50_seconds": 0.0006776000082027167,
        "p95_seconds": 0.0009651999862398952,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.0023721999605186284,
        "p50_seconds": 0.00020290000247769058,
        "p95_seconds": 0.00033569999504834414,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.030914600007236004,
      "cold_index_requests": 4,
      "warm_index_requests": 8
    },
    "by_category": {
      "basic": {
        "total_queries": 2,
        "correct": 2,
        "accuracy": 1.0,
        "key_queries": 2,
        "recalled_at_3": 2,
        "recall_at_3": 1.0,
        "top1_key_correct": 2,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 2,
        "citation_total": 2,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 2,
        "source_set_correct_count": 2,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "isolation": {
        "total_queries": 1,
        "correct": 1,
        "accuracy": 1.0,
        "key_queries": 1,
        "recalled_at_3": 1,
        "recall_at_3": 1.0,
        "top1_key_correct": 1,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 1,
        "citation_total": 1,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 1,
        "source_set_correct_count": 1,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "state": {
        "total_queries": 4,
        "correct": 4,
        "accuracy": 1.0,
        "key_queries": 4,
        "recalled_at_3": 4,
        "recall_at_3": 1.0,
        "top1_key_correct": 4,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 5,
        "citation_total": 5,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 4,
        "source_set_correct_count": 4,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "temporal": {
        "total_queries": 3,
        "correct": 3,
        "accuracy": 1.0,
        "key_queries": 3,
        "recalled_at_3": 3,
        "recall_at_3": 1.0,
        "top1_key_correct": 3,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 3,
        "citation_total": 3,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 3,
        "source_set_correct_count": 3,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "unknown": {
        "total_queries": 2,
        "correct": 2,
        "accuracy": 1.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 2,
        "no_key_correct": 2,
        "no_key_rejection_rate": 1.0,
        "unknown_expected_count": 2,
        "unknown_correct": 2,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 2,
        "source_set_correct_count": 2,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      }
    }
  },
  "mem0": {
    "timings": {
      "index": {
        "n": 12,
        "total_seconds": 3.1044264000374824,
        "p50_seconds": 0.00031060000765137374,
        "p95_seconds": 2.6425434999982826,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 0.08118620002642274,
        "p50_seconds": 0.004035100020701066,
        "p95_seconds": 0.02690870000515133,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.0024704999814275652,
        "p50_seconds": 0.0002227999793831259,
        "p95_seconds": 0.00037799999699927866,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.04533659998560324,
      "cold_index_requests": 4,
      "warm_index_requests": 8
    },
    "by_category": {
      "basic": {
        "total_queries": 2,
        "correct": 2,
        "accuracy": 1.0,
        "key_queries": 2,
        "recalled_at_3": 2,
        "recall_at_3": 1.0,
        "top1_key_correct": 2,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 2,
        "citation_total": 2,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 2,
        "source_set_correct_count": 2,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "isolation": {
        "total_queries": 1,
        "correct": 1,
        "accuracy": 1.0,
        "key_queries": 1,
        "recalled_at_3": 1,
        "recall_at_3": 1.0,
        "top1_key_correct": 1,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 1,
        "citation_total": 1,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 1,
        "source_set_correct_count": 1,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "state": {
        "total_queries": 4,
        "correct": 4,
        "accuracy": 1.0,
        "key_queries": 4,
        "recalled_at_3": 4,
        "recall_at_3": 1.0,
        "top1_key_correct": 4,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 5,
        "citation_total": 5,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 4,
        "source_set_correct_count": 4,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "temporal": {
        "total_queries": 3,
        "correct": 3,
        "accuracy": 1.0,
        "key_queries": 3,
        "recalled_at_3": 3,
        "recall_at_3": 1.0,
        "top1_key_correct": 3,
        "top1_key_accuracy": 1.0,
        "no_key_queries": 0,
        "no_key_correct": 0,
        "no_key_rejection_rate": null,
        "unknown_expected_count": 0,
        "unknown_correct": 0,
        "unknown_information_handling_rate": null,
        "citation_valid": 3,
        "citation_total": 3,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 3,
        "source_set_correct_count": 3,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      },
      "unknown": {
        "total_queries": 2,
        "correct": 2,
        "accuracy": 1.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 2,
        "no_key_correct": 2,
        "no_key_rejection_rate": 1.0,
        "unknown_expected_count": 2,
        "unknown_correct": 2,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 2,
        "source_set_correct_count": 2,
        "failure_stage_counts": {
          "retrieval": 0,
          "resolution": 0,
          "provenance": 0
        }
      }
    }
  }
}
```

## 失败案例

```json
[
  {
    "provider": "no_memory",
    "question_id": "dev-01",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "AsterDocs",
        "text": "What database does AsterDocs use?",
        "as_of": "2026-02-15T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "database"
        ],
        "expected_status": "ok",
        "expected_value": "MySQL",
        "expected_source_ids": [
          "source-aster-db-0"
        ],
        "question_id": "dev-01",
        "category": "basic"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "What database does AsterDocs use?",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "dev-02",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "AsterDocs",
        "text": "三月尚在计划时，database 实际是什么？",
        "as_of": "2026-03-20T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "database"
        ],
        "expected_status": "ok",
        "expected_value": "MySQL",
        "expected_source_ids": [
          "source-aster-db-0"
        ],
        "question_id": "dev-02",
        "category": "temporal"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "三月尚在计划时，database 实际是什么？",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-03-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "dev-03",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "AsterDocs",
        "text": "What database was known on April 2?",
        "as_of": "2026-04-02T23:59:59.999999Z",
        "known_at": "2026-04-02T23:59:59.999999Z",
        "expected_key": [
          "project",
          "database"
        ],
        "expected_status": "ok",
        "expected_value": "MySQL",
        "expected_source_ids": [
          "source-aster-db-0"
        ],
        "question_id": "dev-03",
        "category": "temporal"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "What database was known on April 2?",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": "2026-04-02T23:59:59.999999+00:00",
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "dev-04",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "AsterDocs",
        "text": "用目前全部知识，二月的 framework 是什么？",
        "as_of": "2026-02-15T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "framework"
        ],
        "expected_status": "ok",
        "expected_value": "FastAPI",
        "expected_source_ids": [
          "source-aster-framework-fix"
        ],
        "question_id": "dev-04",
        "category": "state"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "用目前全部知识，二月的 framework 是什么？",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "dev-05",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "AsterDocs",
        "text": "Which language version is confirmed in July?",
        "as_of": "2026-07-01T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "language"
        ],
        "expected_status": "insufficient_evidence",
        "expected_value": null,
        "expected_source_ids": [
          "source-aster-lang-a",
          "source-aster-lang-b"
        ],
        "question_id": "dev-05",
        "category": "state"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "Which language version is confirmed in July?",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "dev-07",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "ParcelNest",
        "text": "ParcelNest language in February?",
        "as_of": "2026-02-15T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "language"
        ],
        "expected_status": "ok",
        "expected_value": "TypeScript 5",
        "expected_source_ids": [
          "source-parcel-lang-0"
        ],
        "question_id": "dev-07",
        "category": "basic"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "ParcelNest",
        "query": "ParcelNest language in February?",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "dev-08",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "ParcelNest",
        "text": "后来补记的 database 在四月二日实际上是什么？",
        "as_of": "2026-04-02T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "database"
        ],
        "expected_status": "ok",
        "expected_value": "PostgreSQL",
        "expected_source_ids": [
          "source-parcel-db-complete"
        ],
        "question_id": "dev-08",
        "category": "temporal"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "ParcelNest",
        "query": "后来补记的 database 在四月二日实际上是什么？",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "dev-09",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "ParcelNest",
        "text": "What framework was known on February 2?",
        "as_of": "2026-02-02T23:59:59.999999Z",
        "known_at": "2026-02-02T23:59:59.999999Z",
        "expected_key": [
          "project",
          "framework"
        ],
        "expected_status": "ok",
        "expected_value": "Express",
        "expected_source_ids": [
          "source-parcel-framework-0"
        ],
        "question_id": "dev-09",
        "category": "state"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "ParcelNest",
        "query": "What framework was known on February 2?",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-02-02T23:59:59.999999+00:00",
        "known_at": "2026-02-02T23:59:59.999999+00:00",
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "dev-10",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "ParcelNest",
        "text": "纠错后重新看二月，framework 应是什么？",
        "as_of": "2026-02-02T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "framework"
        ],
        "expected_status": "ok",
        "expected_value": "NestJS",
        "expected_source_ids": [
          "source-parcel-framework-fix"
        ],
        "question_id": "dev-10",
        "category": "state"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "ParcelNest",
        "query": "纠错后重新看二月，framework 应是什么？",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-02-02T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "dev-11",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "ParcelNest",
        "text": "ParcelNest 的 project database 在一月二十日是什么？",
        "as_of": "2026-01-20T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "database"
        ],
        "expected_status": "ok",
        "expected_value": "SQLite",
        "expected_source_ids": [
          "source-parcel-db-0"
        ],
        "question_id": "dev-11",
        "category": "isolation"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 0,
      "citation_total": 0,
      "citation_checks": [],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "ParcelNest",
        "query": "ParcelNest 的 project database 在一月二十日是什么？",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-01-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  }
]
```
