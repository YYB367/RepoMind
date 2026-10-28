# 阶段目标：V1.2：建立可复现的检索对照、实际用量计量和可读回核验的 Langfuse 追踪/实验

运行 `recorded-holdout-first`；模式 `recorded`。

受控检索比较：相同事实键文档/模型/项目和时间范围，共用 V1 resolver；Mem0 infer=False。

| 方案 | 严格正确 | Recall@3 | 引用合法 | 越界查询 | 实际 API 请求 | 费用估算 |
|---|---:|---:|---:|---:|---:|---|
| repomind_hybrid | 8/8 | 100.0% | 100.0% | 0 | 0 | 未知（not_measured_recorded_vectors） |
| no_memory | 1/8 | 0.0% | N/A | 0 | 0 | 未知（not_measured_recorded_vectors） |
| repomind_semantic | 8/8 | 100.0% | 100.0% | 0 | 0 | 未知（not_measured_recorded_vectors） |
| mem0 | 8/8 | 100.0% | 100.0% | 0 | 0 | 未知（not_measured_recorded_vectors） |

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
  "implementation_sha256": "5447f37ad8c9b5e3638002e5af9cb2f9be57aabcd8d5d1144a63a1ef518e8e25",
  "vector_mode": "recorded",
  "events": {
    "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.2\\events.jsonl",
    "sha256": "55b21fb5a6b5a0ec90dc84d3a48a6a7c1e89bc481a0f63e182b4ecdf2b55e018"
  },
  "dataset": {
    "path": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v1.2\\holdout\\questions.jsonl",
    "sha256": "4cdea0c2b1b55f9d74c613e0cc69215a38add4f530e1e11747ee8494dad3e72f"
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
  "query_count": 8,
  "top_k": 3,
  "min_cosine": 0.2,
  "seed": 0,
  "provider_order": [
    "repomind_hybrid",
    "no_memory",
    "repomind_semantic",
    "mem0"
  ],
  "state_directory": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\work\\v12-runs\\recorded-holdout-first",
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
        "n": 8,
        "total_seconds": 0.03431099996669218,
        "p50_seconds": 0.0005043999990448356,
        "p95_seconds": 0.01976160000776872,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 8,
        "total_seconds": 0.006447599967941642,
        "p50_seconds": 0.0008145000028889626,
        "p95_seconds": 0.0012100999883841723,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 8,
        "total_seconds": 0.0020009000145364553,
        "p50_seconds": 0.0002998000127263367,
        "p95_seconds": 0.00043200000072829425,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.03100570000242442,
      "cold_index_requests": 2,
      "warm_index_requests": 5
    },
    "by_category": {
      "basic": {
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
      "isolation": {
        "total_queries": 1,
        "correct": 1,
        "accuracy": 1.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 1,
        "no_key_correct": 1,
        "no_key_rejection_rate": 1.0,
        "unknown_expected_count": 1,
        "unknown_correct": 1,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
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
        "unknown_expected_count": 1,
        "unknown_correct": 1,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 1,
        "source_set_correct_count": 1,
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
        "n": 8,
        "total_seconds": 5.4000032832846045e-05,
        "p50_seconds": 4.9000082071870565e-06,
        "p95_seconds": 2.1800020476803184e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 8,
        "total_seconds": 0.00030749995494261384,
        "p50_seconds": 3.559998003765941e-05,
        "p95_seconds": 6.049999501556158e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 8,
        "total_seconds": 0.0002279000182170421,
        "p50_seconds": 2.6699999580159783e-05,
        "p95_seconds": 4.639997496269643e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.029938199993921444,
      "cold_index_requests": 0,
      "warm_index_requests": 0
    },
    "by_category": {
      "basic": {
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
      "isolation": {
        "total_queries": 1,
        "correct": 1,
        "accuracy": 1.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 1,
        "no_key_correct": 1,
        "no_key_rejection_rate": 1.0,
        "unknown_expected_count": 1,
        "unknown_correct": 1,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
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
        "unknown_expected_count": 1,
        "unknown_correct": 0,
        "unknown_information_handling_rate": 0.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 1,
        "source_set_correct_count": 1,
        "failure_stage_counts": {
          "retrieval": 1,
          "resolution": 0,
          "provenance": 0
        }
      }
    }
  },
  "repomind_semantic": {
    "timings": {
      "index": {
        "n": 8,
        "total_seconds": 0.026374600012786686,
        "p50_seconds": 0.0005790000141132623,
        "p95_seconds": 0.011732299986761063,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 8,
        "total_seconds": 0.005443799978820607,
        "p50_seconds": 0.0006553999846801162,
        "p95_seconds": 0.001111799996579066,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 8,
        "total_seconds": 0.0015241999935824424,
        "p50_seconds": 0.00019920000340789557,
        "p95_seconds": 0.00029379999614320695,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.030494000006001443,
      "cold_index_requests": 2,
      "warm_index_requests": 5
    },
    "by_category": {
      "basic": {
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
      "isolation": {
        "total_queries": 1,
        "correct": 1,
        "accuracy": 1.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 1,
        "no_key_correct": 1,
        "no_key_rejection_rate": 1.0,
        "unknown_expected_count": 1,
        "unknown_correct": 1,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
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
        "unknown_expected_count": 1,
        "unknown_correct": 1,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 1,
        "source_set_correct_count": 1,
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
        "n": 8,
        "total_seconds": 2.6636728999437764,
        "p50_seconds": 0.00046999999904073775,
        "p95_seconds": 2.5108191999897826,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 8,
        "total_seconds": 0.05089120002230629,
        "p50_seconds": 0.00463300000410527,
        "p95_seconds": 0.019077500008279458,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 8,
        "total_seconds": 0.002329400012968108,
        "p50_seconds": 0.0002652000111993402,
        "p95_seconds": 0.0004687000182457268,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.04539899999508634,
      "cold_index_requests": 2,
      "warm_index_requests": 5
    },
    "by_category": {
      "basic": {
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
      "isolation": {
        "total_queries": 1,
        "correct": 1,
        "accuracy": 1.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 1,
        "no_key_correct": 1,
        "no_key_rejection_rate": 1.0,
        "unknown_expected_count": 1,
        "unknown_correct": 1,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
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
        "unknown_expected_count": 1,
        "unknown_correct": 1,
        "unknown_information_handling_rate": 1.0,
        "citation_valid": 0,
        "citation_total": 0,
        "source_validity": null,
        "project_leakage_count": 0,
        "answer_correct_count": 1,
        "source_set_correct_count": 1,
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
    "question_id": "holdout-01",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "CedarTrack",
        "text": "What was the database used by CedarTrack in February?",
        "as_of": "2026-02-10T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "database"
        ],
        "expected_status": "ok",
        "expected_value": "MariaDB",
        "expected_source_ids": [
          "source-cedar-db-0"
        ],
        "question_id": "holdout-01",
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
        "project_id": "CedarTrack",
        "query": "What was the database used by CedarTrack in February?",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-02-10T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "holdout-02",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "CedarTrack",
        "text": "CedarTrack 三月的 database 已迁移了吗？",
        "as_of": "2026-03-20T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "database"
        ],
        "expected_status": "ok",
        "expected_value": "MariaDB",
        "expected_source_ids": [
          "source-cedar-db-0"
        ],
        "question_id": "holdout-02",
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
        "project_id": "CedarTrack",
        "query": "CedarTrack 三月的 database 已迁移了吗？",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-03-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "holdout-03",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "CedarTrack",
        "text": "Using current evidence, which database was effective April 2?",
        "as_of": "2026-04-02T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "database"
        ],
        "expected_status": "ok",
        "expected_value": "PostgreSQL",
        "expected_source_ids": [
          "source-cedar-db-complete"
        ],
        "question_id": "holdout-03",
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
        "project_id": "CedarTrack",
        "query": "Using current evidence, which database was effective April 2?",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "holdout-04",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "CedarTrack",
        "text": "截至四月二日已知的 database 是什么？",
        "as_of": "2026-04-02T23:59:59.999999Z",
        "known_at": "2026-04-02T23:59:59.999999Z",
        "expected_key": [
          "project",
          "database"
        ],
        "expected_status": "ok",
        "expected_value": "MariaDB",
        "expected_source_ids": [
          "source-cedar-db-0"
        ],
        "question_id": "holdout-04",
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
        "project_id": "CedarTrack",
        "query": "截至四月二日已知的 database 是什么？",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-04-02T23:59:59.999999+00:00",
        "known_at": "2026-04-02T23:59:59.999999+00:00",
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "holdout-05",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "CedarTrack",
        "text": "Which framework actually applied in February after the correction?",
        "as_of": "2026-02-10T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "framework"
        ],
        "expected_status": "ok",
        "expected_value": "Gin",
        "expected_source_ids": [
          "source-cedar-framework-fix"
        ],
        "question_id": "holdout-05",
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
        "project_id": "CedarTrack",
        "query": "Which framework actually applied in February after the correction?",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-02-10T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "holdout-06",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "CedarTrack",
        "text": "CedarTrack language 在七月有确定版本吗？",
        "as_of": "2026-07-01T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "language"
        ],
        "expected_status": "insufficient_evidence",
        "expected_value": null,
        "expected_source_ids": [
          "source-cedar-lang-a",
          "source-cedar-lang-b"
        ],
        "question_id": "holdout-06",
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
        "project_id": "CedarTrack",
        "query": "CedarTrack language 在七月有确定版本吗？",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  },
  {
    "provider": "no_memory",
    "question_id": "holdout-07",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "CedarTrack",
        "text": "一月二十日 deployment 已采用什么？",
        "as_of": "2026-01-20T23:59:59.999999Z",
        "known_at": null,
        "expected_key": [
          "project",
          "deployment"
        ],
        "expected_status": "unknown",
        "expected_value": null,
        "expected_source_ids": [],
        "question_id": "holdout-07",
        "category": "unknown"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": true,
      "sources_correct": true,
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
        "project_id": "CedarTrack",
        "query": "一月二十日 deployment 已采用什么？",
        "mode": "no_memory",
        "provider": "no_memory",
        "as_of": "2026-01-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 0,
        "hits": [],
        "reason": "no_memory_baseline"
      }
    }
  }
]
```
