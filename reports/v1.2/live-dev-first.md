# 阶段目标：V1.2：建立可复现的检索对照、实际用量计量和可读回核验的 Langfuse 追踪/实验

运行 `live-dev-first`；模式 `live`。

受控检索比较：相同事实键文档/模型/项目和时间范围，共用 V1 resolver；Mem0 infer=False。

| 方案 | 严格正确 | Recall@3 | 引用合法 | 越界查询 | 实际 API 请求 | 费用估算 |
|---|---:|---:|---:|---:|---:|---|
| repomind_hybrid | 7/12 | 100.0% | 100.0% | 0 | 16 | 未知（no_price_card） |
| no_memory | 2/12 | 0.0% | N/A | 0 | 0 | 未知（usage_not_proven_complete） |
| repomind_semantic | 2/12 | 0.0% | N/A | 0 | 16 | 未知（no_price_card） |
| mem0 | 2/12 | 0.0% | N/A | 0 | 32 | 未知（no_price_card） |

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
  "vector_mode": "live",
  "events": {
    "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.2\\events.jsonl",
    "sha256": "55b21fb5a6b5a0ec90dc84d3a48a6a7c1e89bc481a0f63e182b4ecdf2b55e018"
  },
  "dataset": {
    "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.2\\dev\\questions.jsonl",
    "sha256": "359f126b0963c42dc8d8c12cf9ee333938d6bab8361d38ab6b569d4678f2bc2f"
  },
  "vectors": null,
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
  "state_directory": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\work\\v12-runs\\live-dev-first",
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
        "total_seconds": 2.5888085999176838,
        "p50_seconds": 0.004447700019227341,
        "p95_seconds": 0.7120954999991227,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 4.622751700022491,
        "p50_seconds": 0.37601900001754984,
        "p95_seconds": 0.4766688000236172,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.003243300103349611,
        "p50_seconds": 0.0002846000134013593,
        "p95_seconds": 0.0004610000178217888,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.07105719999526627,
      "cold_index_requests": 4,
      "warm_index_requests": 8
    },
    "by_category": {
      "basic": {
        "total_queries": 2,
        "correct": 1,
        "accuracy": 0.5,
        "key_queries": 2,
        "recalled_at_3": 2,
        "recall_at_3": 1.0,
        "top1_key_correct": 1,
        "top1_key_accuracy": 0.5,
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
        "answer_correct_count": 1,
        "source_set_correct_count": 1,
        "failure_stage_counts": {
          "retrieval": 1,
          "resolution": 0,
          "provenance": 0
        }
      },
      "isolation": {
        "total_queries": 1,
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 1,
        "recalled_at_3": 1,
        "recall_at_3": 1.0,
        "top1_key_correct": 0,
        "top1_key_accuracy": 0.0,
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
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 3,
        "recalled_at_3": 3,
        "recall_at_3": 1.0,
        "top1_key_correct": 0,
        "top1_key_accuracy": 0.0,
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
  "no_memory": {
    "timings": {
      "index": {
        "n": 12,
        "total_seconds": 8.300002082251012e-05,
        "p50_seconds": 4.6000059228390455e-06,
        "p95_seconds": 2.370000584051013e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 0.00046549999387934804,
        "p50_seconds": 3.250001464039087e-05,
        "p95_seconds": 5.609999061562121e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.00037759996484965086,
        "p50_seconds": 2.609999501146376e-05,
        "p95_seconds": 5.420000525191426e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.03073269999003969,
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
        "total_seconds": 2.1473296999756712,
        "p50_seconds": 0.004496499983360991,
        "p95_seconds": 0.5668319999822415,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 4.909642199985683,
        "p50_seconds": 0.40183359998627566,
        "p95_seconds": 0.5035206000029575,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.0005544000014197081,
        "p50_seconds": 3.819999983534217e-05,
        "p95_seconds": 0.0001399999891873449,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.05976519998512231,
      "cold_index_requests": 4,
      "warm_index_requests": 8
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
  "mem0": {
    "timings": {
      "index": {
        "n": 12,
        "total_seconds": 11.679337300069164,
        "p50_seconds": 0.0003910000086762011,
        "p95_seconds": 4.960604599997168,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 5.6356396000192035,
        "p50_seconds": 0.4254580000124406,
        "p95_seconds": 0.7359260999946855,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.00038389998371712863,
        "p50_seconds": 3.0499999411404133e-05,
        "p95_seconds": 4.260000423528254e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.07253479998325929,
      "cold_index_requests": 4,
      "warm_index_requests": 8
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
  }
}
```

## 失败案例

```json
[
  {
    "provider": "repomind_hybrid",
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
      "rank": 2,
      "recalled_at_3": true,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "Redis",
      "actual_source_ids": [
        "source-aster-worker-db"
      ],
      "citation_valid": 2,
      "citation_total": 2,
      "citation_checks": [
        {
          "event_id": "aster-worker-db",
          "source_id": "source-aster-worker-db",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "aster-db-0",
          "source_id": "source-aster-db-0",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "What database does AsterDocs use?",
        "mode": "hybrid",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "worker",
            "predicate": "database",
            "score": 0.01639344262295082,
            "lexical_score": 0.14142135623730948,
            "semantic_score": 0.5104454018804349,
            "result": {
              "status": "ok",
              "value": "Redis",
              "evidence": [
                {
                  "event_id": "aster-worker-db",
                  "project_id": "AsterDocs",
                  "subject": "worker",
                  "predicate": "database",
                  "value": "Redis",
                  "event_type": "declare",
                  "observed_at": "2026-01-15T00:00:00Z",
                  "effective_at": "2026-01-15T00:00:00Z",
                  "source_id": "source-aster-worker-db",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-worker-db"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.016129032258064516,
            "lexical_score": 0.06741998624632421,
            "semantic_score": 0.4986009045938354,
            "result": {
              "status": "ok",
              "value": "MySQL",
              "evidence": [
                {
                  "event_id": "aster-db-0",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "database",
                  "value": "MySQL",
                  "event_type": "declare",
                  "observed_at": "2026-01-01T00:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-aster-db-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-db-0",
                "aster-db-complete",
                "aster-db-plan"
              ],
              "plan_event_ids": []
            }
          }
        ],
        "provider": "repomind_hybrid"
      }
    }
  },
  {
    "provider": "repomind_hybrid",
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
      "rank": 2,
      "recalled_at_3": true,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "Redis",
      "actual_source_ids": [
        "source-aster-worker-db"
      ],
      "citation_valid": 2,
      "citation_total": 2,
      "citation_checks": [
        {
          "event_id": "aster-worker-db",
          "source_id": "source-aster-worker-db",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "aster-db-0",
          "source_id": "source-aster-db-0",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "三月尚在计划时，database 实际是什么？",
        "mode": "hybrid",
        "as_of": "2026-03-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "worker",
            "predicate": "database",
            "score": 0.01639344262295082,
            "lexical_score": 0.09534625892455924,
            "semantic_score": 0.3120432124112391,
            "result": {
              "status": "ok",
              "value": "Redis",
              "evidence": [
                {
                  "event_id": "aster-worker-db",
                  "project_id": "AsterDocs",
                  "subject": "worker",
                  "predicate": "database",
                  "value": "Redis",
                  "event_type": "declare",
                  "observed_at": "2026-01-15T00:00:00Z",
                  "effective_at": "2026-01-15T00:00:00Z",
                  "source_id": "source-aster-worker-db",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-worker-db"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.016129032258064516,
            "lexical_score": 0.045454545454545456,
            "semantic_score": 0.45156826386120996,
            "result": {
              "status": "ok",
              "value": "MySQL",
              "evidence": [
                {
                  "event_id": "aster-db-0",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "database",
                  "value": "MySQL",
                  "event_type": "declare",
                  "observed_at": "2026-01-01T00:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-aster-db-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-db-0",
                "aster-db-complete",
                "aster-db-plan"
              ],
              "plan_event_ids": [
                "aster-db-plan"
              ]
            }
          }
        ],
        "provider": "repomind_hybrid"
      }
    }
  },
  {
    "provider": "repomind_hybrid",
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
      "rank": 2,
      "recalled_at_3": true,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "Redis",
      "actual_source_ids": [
        "source-aster-worker-db"
      ],
      "citation_valid": 2,
      "citation_total": 2,
      "citation_checks": [
        {
          "event_id": "aster-worker-db",
          "source_id": "source-aster-worker-db",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "aster-db-0",
          "source_id": "source-aster-db-0",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "What database was known on April 2?",
        "mode": "hybrid",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": "2026-04-02T23:59:59.999999+00:00",
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "worker",
            "predicate": "database",
            "score": 0.01639344262295082,
            "lexical_score": 0.11952286093343936,
            "semantic_score": 0.37403738196997327,
            "result": {
              "status": "ok",
              "value": "Redis",
              "evidence": [
                {
                  "event_id": "aster-worker-db",
                  "project_id": "AsterDocs",
                  "subject": "worker",
                  "predicate": "database",
                  "value": "Redis",
                  "event_type": "declare",
                  "observed_at": "2026-01-15T00:00:00Z",
                  "effective_at": "2026-01-15T00:00:00Z",
                  "source_id": "source-aster-worker-db",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-worker-db"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.016129032258064516,
            "lexical_score": 0.08058229640253803,
            "semantic_score": 0.39263292176280756,
            "result": {
              "status": "ok",
              "value": "MySQL",
              "evidence": [
                {
                  "event_id": "aster-db-0",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "database",
                  "value": "MySQL",
                  "event_type": "declare",
                  "observed_at": "2026-01-01T00:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-aster-db-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-db-0",
                "aster-db-plan"
              ],
              "plan_event_ids": [
                "aster-db-plan"
              ]
            }
          }
        ],
        "provider": "repomind_hybrid"
      }
    }
  },
  {
    "provider": "repomind_hybrid",
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
      "rank": 2,
      "recalled_at_3": true,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "MongoDB",
      "actual_source_ids": [
        "source-parcel-worker-db"
      ],
      "citation_valid": 2,
      "citation_total": 2,
      "citation_checks": [
        {
          "event_id": "parcel-worker-db",
          "source_id": "source-parcel-worker-db",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-db-complete",
          "source_id": "source-parcel-db-complete",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "ParcelNest",
        "query": "后来补记的 database 在四月二日实际上是什么？",
        "mode": "hybrid",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "worker",
            "predicate": "database",
            "score": 0.01639344262295082,
            "lexical_score": 0.0816496580927726,
            "semantic_score": 0.30411291305646887,
            "result": {
              "status": "ok",
              "value": "MongoDB",
              "evidence": [
                {
                  "event_id": "parcel-worker-db",
                  "project_id": "ParcelNest",
                  "subject": "worker",
                  "predicate": "database",
                  "value": "MongoDB",
                  "event_type": "declare",
                  "observed_at": "2026-01-15T00:00:00Z",
                  "effective_at": "2026-01-15T00:00:00Z",
                  "source_id": "source-parcel-worker-db",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-worker-db"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.016129032258064516,
            "lexical_score": 0.03892494720807615,
            "semantic_score": 0.3766887216025014,
            "result": {
              "status": "ok",
              "value": "PostgreSQL",
              "evidence": [
                {
                  "event_id": "parcel-db-complete",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "database",
                  "value": "PostgreSQL",
                  "event_type": "complete",
                  "observed_at": "2026-04-05T10:00:00Z",
                  "effective_at": "2026-04-01T00:00:00Z",
                  "source_id": "source-parcel-db-complete",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-db-0",
                "parcel-db-complete",
                "parcel-db-plan"
              ],
              "plan_event_ids": [
                "parcel-db-plan"
              ]
            }
          }
        ],
        "provider": "repomind_hybrid"
      }
    }
  },
  {
    "provider": "repomind_hybrid",
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
      "rank": 3,
      "recalled_at_3": true,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "unknown",
      "actual_value": null,
      "actual_source_ids": [],
      "citation_valid": 2,
      "citation_total": 2,
      "citation_checks": [
        {
          "event_id": "parcel-worker-db",
          "source_id": "source-parcel-worker-db",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-db-0",
          "source_id": "source-parcel-db-0",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "ParcelNest",
        "query": "ParcelNest 的 project database 在一月二十日是什么？",
        "mode": "hybrid",
        "as_of": "2026-01-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.01639344262295082,
            "lexical_score": 0.09128709291752768,
            "semantic_score": 0.4183060367825612,
            "result": {
              "status": "unknown",
              "value": null,
              "evidence": [],
              "reason": "no_effective_fact",
              "considered_event_ids": [
                "parcel-deployment-0"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "worker",
            "predicate": "database",
            "score": 0.016129032258064516,
            "lexical_score": 0.09128709291752768,
            "semantic_score": 0.3620701389883807,
            "result": {
              "status": "ok",
              "value": "MongoDB",
              "evidence": [
                {
                  "event_id": "parcel-worker-db",
                  "project_id": "ParcelNest",
                  "subject": "worker",
                  "predicate": "database",
                  "value": "MongoDB",
                  "event_type": "declare",
                  "observed_at": "2026-01-15T00:00:00Z",
                  "effective_at": "2026-01-15T00:00:00Z",
                  "source_id": "source-parcel-worker-db",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-worker-db"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.015873015873015872,
            "lexical_score": 0.08703882797784893,
            "semantic_score": 0.4244917233116925,
            "result": {
              "status": "ok",
              "value": "SQLite",
              "evidence": [
                {
                  "event_id": "parcel-db-0",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "database",
                  "value": "SQLite",
                  "event_type": "declare",
                  "observed_at": "2026-01-01T00:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-db-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-db-0",
                "parcel-db-complete",
                "parcel-db-plan"
              ],
              "plan_event_ids": []
            }
          }
        ],
        "provider": "repomind_hybrid"
      }
    }
  },
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
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-03-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": "2026-04-02T23:59:59.999999+00:00",
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-02-02T23:59:59.999999+00:00",
        "known_at": "2026-02-02T23:59:59.999999+00:00",
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-02-02T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
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
        "mode": "semantic",
        "as_of": "2026-01-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "AsterDocs",
        "query": "What database does AsterDocs use?",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-bdd4435550d2a88924c4b712ee984c511a9e62dda1c24904027aa9d87b1167b8",
        "hits": []
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "AsterDocs",
        "query": "三月尚在计划时，database 实际是什么？",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-03-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-bdd4435550d2a88924c4b712ee984c511a9e62dda1c24904027aa9d87b1167b8",
        "hits": []
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "AsterDocs",
        "query": "What database was known on April 2?",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": "2026-04-02T23:59:59.999999+00:00",
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-87febbb48b053159e66e99d3f93bb7b144e8ee896102309a90bc830ef76331a7",
        "hits": []
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "AsterDocs",
        "query": "用目前全部知识，二月的 framework 是什么？",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-bdd4435550d2a88924c4b712ee984c511a9e62dda1c24904027aa9d87b1167b8",
        "hits": []
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "AsterDocs",
        "query": "Which language version is confirmed in July?",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-bdd4435550d2a88924c4b712ee984c511a9e62dda1c24904027aa9d87b1167b8",
        "hits": []
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "ParcelNest",
        "query": "ParcelNest language in February?",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-cc01ca3b517e01268a34a6872f685b9d56ef9d22805413ddd0c1725d6ed75029",
        "hits": []
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "ParcelNest",
        "query": "后来补记的 database 在四月二日实际上是什么？",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-cc01ca3b517e01268a34a6872f685b9d56ef9d22805413ddd0c1725d6ed75029",
        "hits": []
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "ParcelNest",
        "query": "What framework was known on February 2?",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-02-02T23:59:59.999999+00:00",
        "known_at": "2026-02-02T23:59:59.999999+00:00",
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-2117a49d04a8cb908d6b501083ffe7b98c7e784387e4555e165be234389222ea",
        "hits": []
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "ParcelNest",
        "query": "纠错后重新看二月，framework 应是什么？",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-02-02T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-cc01ca3b517e01268a34a6872f685b9d56ef9d22805413ddd0c1725d6ed75029",
        "hits": []
      }
    }
  },
  {
    "provider": "mem0",
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
        "provider": "mem0",
        "project_id": "ParcelNest",
        "query": "ParcelNest 的 project database 在一月二十日是什么？",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-01-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.55,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-cc01ca3b517e01268a34a6872f685b9d56ef9d22805413ddd0c1725d6ed75029",
        "hits": []
      }
    }
  }
]
```
