# 阶段目标：V1.2：建立可复现的检索对照、实际用量计量和可读回核验的 Langfuse 追踪/实验

运行 `live-dev-cutoff-020`；模式 `live`。

受控检索比较：相同事实键文档/模型/项目和时间范围，共用 V1 resolver；Mem0 infer=False。

| 方案 | 严格正确 | Recall@3 | 引用合法 | 越界查询 | 实际 API 请求 | 费用估算 |
|---|---:|---:|---:|---:|---:|---|
| repomind_hybrid | 8/12 | 100.0% | 100.0% | 0 | 16 | 未知（no_price_card） |
| no_memory | 2/12 | 0.0% | N/A | 0 | 0 | 未知（usage_not_proven_complete） |
| repomind_semantic | 7/12 | 100.0% | 100.0% | 0 | 16 | 未知（no_price_card） |
| mem0 | 7/12 | 100.0% | 100.0% | 0 | 32 | 未知（no_price_card） |

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
  "min_cosine": 0.2,
  "seed": 0,
  "provider_order": [
    "repomind_hybrid",
    "no_memory",
    "repomind_semantic",
    "mem0"
  ],
  "state_directory": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\work\\v12-runs\\live-dev-cutoff-020",
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
        "total_seconds": 2.311696999997366,
        "p50_seconds": 0.004603200010024011,
        "p95_seconds": 0.6826102999912109,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 4.596151300007477,
        "p50_seconds": 0.370805599988671,
        "p95_seconds": 0.4925082999980077,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.0065709000919014215,
        "p50_seconds": 0.0005224000196903944,
        "p95_seconds": 0.0009600999765098095,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.0744581000180915,
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
        "citation_valid": 6,
        "citation_total": 6,
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
        "citation_valid": 13,
        "citation_total": 13,
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
        "citation_valid": 9,
        "citation_total": 9,
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
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 2,
        "no_key_correct": 0,
        "no_key_rejection_rate": 0.0,
        "unknown_expected_count": 2,
        "unknown_correct": 0,
        "unknown_information_handling_rate": 0.0,
        "citation_valid": 6,
        "citation_total": 6,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 0,
        "source_set_correct_count": 0,
        "failure_stage_counts": {
          "retrieval": 2,
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
        "total_seconds": 9.390004561282694e-05,
        "p50_seconds": 4.6000059228390455e-06,
        "p95_seconds": 3.300001844763756e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 0.0004695000243373215,
        "p50_seconds": 3.3899996196851134e-05,
        "p95_seconds": 5.740000051446259e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.0003410999779589474,
        "p50_seconds": 2.6900001103058457e-05,
        "p95_seconds": 3.6600016755983233e-05,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.030750300007639453,
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
        "total_seconds": 2.141615400003502,
        "p50_seconds": 0.0044132999901194125,
        "p95_seconds": 0.659371400019154,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 4.896593300014501,
        "p50_seconds": 0.38895990001037717,
        "p95_seconds": 0.5543505999958143,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.006261999980779365,
        "p50_seconds": 0.0005123999726492912,
        "p95_seconds": 0.0006184999947436154,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.05942420000792481,
      "cold_index_requests": 4,
      "warm_index_requests": 8
    },
    "by_category": {
      "basic": {
        "total_queries": 2,
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 2,
        "recalled_at_3": 2,
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
        "citation_valid": 13,
        "citation_total": 13,
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
        "citation_valid": 9,
        "citation_total": 9,
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
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 2,
        "no_key_correct": 0,
        "no_key_rejection_rate": 0.0,
        "unknown_expected_count": 2,
        "unknown_correct": 0,
        "unknown_information_handling_rate": 0.0,
        "citation_valid": 6,
        "citation_total": 6,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 0,
        "source_set_correct_count": 0,
        "failure_stage_counts": {
          "retrieval": 2,
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
        "total_seconds": 11.792375699878903,
        "p50_seconds": 0.0004529999860096723,
        "p95_seconds": 4.8290834999934305,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "search_and_resolution": {
        "n": 12,
        "total_seconds": 5.392429200030165,
        "p50_seconds": 0.432005599985132,
        "p95_seconds": 0.6824247000040486,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "scoring": {
        "n": 12,
        "total_seconds": 0.008315900020534173,
        "p50_seconds": 0.0006749000167474151,
        "p95_seconds": 0.0010737999982666224,
        "percentile_method": "nearest-rank; small-sample descriptive only"
      },
      "setup_seconds": 0.07812309998553246,
      "cold_index_requests": 4,
      "warm_index_requests": 8
    },
    "by_category": {
      "basic": {
        "total_queries": 2,
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 2,
        "recalled_at_3": 2,
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
        "citation_valid": 13,
        "citation_total": 13,
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
        "citation_valid": 9,
        "citation_total": 9,
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
        "correct": 0,
        "accuracy": 0.0,
        "key_queries": 0,
        "recalled_at_3": 0,
        "recall_at_3": null,
        "top1_key_correct": 0,
        "top1_key_accuracy": null,
        "no_key_queries": 2,
        "no_key_correct": 0,
        "no_key_rejection_rate": 0.0,
        "unknown_expected_count": 2,
        "unknown_correct": 0,
        "unknown_information_handling_rate": 0.0,
        "citation_valid": 6,
        "citation_total": 6,
        "source_validity": 1.0,
        "project_leakage_count": 0,
        "answer_correct_count": 0,
        "source_set_correct_count": 0,
        "failure_stage_counts": {
          "retrieval": 2,
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
      "citation_valid": 3,
      "citation_total": 3,
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
        },
        {
          "event_id": "aster-deployment-0",
          "source_id": "source-aster-deployment-0",
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
        "min_cosine": 0.2,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "worker",
            "predicate": "database",
            "score": 0.03278688524590164,
            "lexical_score": 0.14142135623730948,
            "semantic_score": 0.5082124208603506,
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
            "score": 0.03225806451612903,
            "lexical_score": 0.06741998624632421,
            "semantic_score": 0.49714375933341204,
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
          },
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.015873015873015872,
            "lexical_score": 0.0,
            "semantic_score": 0.44547164345145596,
            "result": {
              "status": "ok",
              "value": "Docker",
              "evidence": [
                {
                  "event_id": "aster-deployment-0",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "deployment",
                  "value": "Docker",
                  "event_type": "declare",
                  "observed_at": "2026-02-01T00:00:00Z",
                  "effective_at": "2026-02-01T00:00:00Z",
                  "source_id": "source-aster-deployment-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-deployment-0"
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
    "question_id": "dev-06",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "AsterDocs",
        "text": "AsterDocs 的 billing_service 使用哪个服务？",
        "as_of": "2026-07-01T23:59:59.999999Z",
        "known_at": null,
        "expected_key": null,
        "expected_status": "unknown",
        "expected_value": null,
        "expected_source_ids": [],
        "question_id": "dev-06",
        "category": "unknown"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "Docker",
      "actual_source_ids": [
        "source-aster-deployment-0"
      ],
      "citation_valid": 3,
      "citation_total": 3,
      "citation_checks": [
        {
          "event_id": "aster-deployment-0",
          "source_id": "source-aster-deployment-0",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "aster-framework-fix",
          "source_id": "source-aster-framework-fix",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "aster-db-complete",
          "source_id": "source-aster-db-complete",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "AsterDocs 的 billing_service 使用哪个服务？",
        "mode": "hybrid",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.01639344262295082,
            "lexical_score": 0.0,
            "semantic_score": 0.3999449973717966,
            "result": {
              "status": "ok",
              "value": "Docker",
              "evidence": [
                {
                  "event_id": "aster-deployment-0",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "deployment",
                  "value": "Docker",
                  "event_type": "declare",
                  "observed_at": "2026-02-01T00:00:00Z",
                  "effective_at": "2026-02-01T00:00:00Z",
                  "source_id": "source-aster-deployment-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-deployment-0"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.016129032258064516,
            "lexical_score": 0.0,
            "semantic_score": 0.3964481126858616,
            "result": {
              "status": "ok",
              "value": "FastAPI",
              "evidence": [
                {
                  "event_id": "aster-framework-fix",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "FastAPI",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-aster-framework-fix",
                  "supersedes_event_id": "aster-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-framework-0",
                "aster-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.015873015873015872,
            "lexical_score": 0.0,
            "semantic_score": 0.3897421484437034,
            "result": {
              "status": "ok",
              "value": "PostgreSQL",
              "evidence": [
                {
                  "event_id": "aster-db-complete",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "database",
                  "value": "PostgreSQL",
                  "event_type": "complete",
                  "observed_at": "2026-04-05T10:00:00Z",
                  "effective_at": "2026-04-01T00:00:00Z",
                  "source_id": "source-aster-db-complete",
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
          "event_id": "parcel-framework-fix",
          "source_id": "source-parcel-framework-fix",
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
        "min_cosine": 0.2,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.032266458495966696,
            "lexical_score": 0.09128709291752768,
            "semantic_score": 0.4176571489054152,
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
            "subject": "project",
            "predicate": "framework",
            "score": 0.032018442622950824,
            "lexical_score": 0.05892556509887897,
            "semantic_score": 0.45370190863922577,
            "result": {
              "status": "ok",
              "value": "NestJS",
              "evidence": [
                {
                  "event_id": "parcel-framework-fix",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "NestJS",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-framework-fix",
                  "supersedes_event_id": "parcel-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-framework-0",
                "parcel-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.03200204813108039,
            "lexical_score": 0.08703882797784893,
            "semantic_score": 0.42643058541918083,
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
    "provider": "repomind_hybrid",
    "question_id": "dev-12",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "ParcelNest",
        "text": "Which cache_service has ParcelNest adopted?",
        "as_of": "2026-07-01T23:59:59.999999Z",
        "known_at": null,
        "expected_key": null,
        "expected_status": "unknown",
        "expected_value": null,
        "expected_source_ids": [],
        "question_id": "dev-12",
        "category": "unknown"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "NestJS",
      "actual_source_ids": [
        "source-parcel-framework-fix"
      ],
      "citation_valid": 3,
      "citation_total": 3,
      "citation_checks": [
        {
          "event_id": "parcel-framework-fix",
          "source_id": "source-parcel-framework-fix",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-db-complete",
          "source_id": "source-parcel-db-complete",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-deployment-0",
          "source_id": "source-parcel-deployment-0",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "ParcelNest",
        "query": "Which cache_service has ParcelNest adopted?",
        "mode": "hybrid",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.01639344262295082,
            "lexical_score": 0.0,
            "semantic_score": 0.5088952514581704,
            "result": {
              "status": "ok",
              "value": "NestJS",
              "evidence": [
                {
                  "event_id": "parcel-framework-fix",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "NestJS",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-framework-fix",
                  "supersedes_event_id": "parcel-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-framework-0",
                "parcel-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.016129032258064516,
            "lexical_score": 0.0,
            "semantic_score": 0.3695018788502077,
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
          },
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.015873015873015872,
            "lexical_score": 0.0,
            "semantic_score": 0.3473622720775522,
            "result": {
              "status": "ok",
              "value": "Docker",
              "evidence": [
                {
                  "event_id": "parcel-deployment-0",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "deployment",
                  "value": "Docker",
                  "event_type": "declare",
                  "observed_at": "2026-02-01T00:00:00Z",
                  "effective_at": "2026-02-01T00:00:00Z",
                  "source_id": "source-parcel-deployment-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-deployment-0"
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
        "min_cosine": 0.2,
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
        "min_cosine": 0.2,
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
        "min_cosine": 0.2,
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
        "min_cosine": 0.2,
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
        "min_cosine": 0.2,
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
        "min_cosine": 0.2,
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
        "min_cosine": 0.2,
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
        "min_cosine": 0.2,
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
        "min_cosine": 0.2,
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
        "min_cosine": 0.2,
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
      "citation_valid": 3,
      "citation_total": 3,
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
        },
        {
          "event_id": "aster-deployment-0",
          "source_id": "source-aster-deployment-0",
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
        "mode": "semantic",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "worker",
            "predicate": "database",
            "score": 0.5131788815238609,
            "lexical_score": 0.0,
            "semantic_score": 0.5131788815238609,
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
            "score": 0.4961040046152832,
            "lexical_score": 0.0,
            "semantic_score": 0.4961040046152832,
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
          },
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.4520009652900367,
            "lexical_score": 0.0,
            "semantic_score": 0.4520009652900367,
            "result": {
              "status": "ok",
              "value": "Docker",
              "evidence": [
                {
                  "event_id": "aster-deployment-0",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "deployment",
                  "value": "Docker",
                  "event_type": "declare",
                  "observed_at": "2026-02-01T00:00:00Z",
                  "effective_at": "2026-02-01T00:00:00Z",
                  "source_id": "source-aster-deployment-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-deployment-0"
              ],
              "plan_event_ids": []
            }
          }
        ],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
    "question_id": "dev-06",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "AsterDocs",
        "text": "AsterDocs 的 billing_service 使用哪个服务？",
        "as_of": "2026-07-01T23:59:59.999999Z",
        "known_at": null,
        "expected_key": null,
        "expected_status": "unknown",
        "expected_value": null,
        "expected_source_ids": [],
        "question_id": "dev-06",
        "category": "unknown"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "Docker",
      "actual_source_ids": [
        "source-aster-deployment-0"
      ],
      "citation_valid": 3,
      "citation_total": 3,
      "citation_checks": [
        {
          "event_id": "aster-deployment-0",
          "source_id": "source-aster-deployment-0",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "aster-framework-fix",
          "source_id": "source-aster-framework-fix",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "aster-db-complete",
          "source_id": "source-aster-db-complete",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "AsterDocs",
        "query": "AsterDocs 的 billing_service 使用哪个服务？",
        "mode": "semantic",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.40354367586008544,
            "lexical_score": 0.0,
            "semantic_score": 0.40354367586008544,
            "result": {
              "status": "ok",
              "value": "Docker",
              "evidence": [
                {
                  "event_id": "aster-deployment-0",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "deployment",
                  "value": "Docker",
                  "event_type": "declare",
                  "observed_at": "2026-02-01T00:00:00Z",
                  "effective_at": "2026-02-01T00:00:00Z",
                  "source_id": "source-aster-deployment-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-deployment-0"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.39479028358740026,
            "lexical_score": 0.0,
            "semantic_score": 0.39479028358740026,
            "result": {
              "status": "ok",
              "value": "FastAPI",
              "evidence": [
                {
                  "event_id": "aster-framework-fix",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "FastAPI",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-aster-framework-fix",
                  "supersedes_event_id": "aster-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-framework-0",
                "aster-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.39388629168625233,
            "lexical_score": 0.0,
            "semantic_score": 0.39388629168625233,
            "result": {
              "status": "ok",
              "value": "PostgreSQL",
              "evidence": [
                {
                  "event_id": "aster-db-complete",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "database",
                  "value": "PostgreSQL",
                  "event_type": "complete",
                  "observed_at": "2026-04-05T10:00:00Z",
                  "effective_at": "2026-04-01T00:00:00Z",
                  "source_id": "source-aster-db-complete",
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
      "rank": 2,
      "recalled_at_3": true,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "NestJS",
      "actual_source_ids": [
        "source-parcel-framework-fix"
      ],
      "citation_valid": 3,
      "citation_total": 3,
      "citation_checks": [
        {
          "event_id": "parcel-framework-fix",
          "source_id": "source-parcel-framework-fix",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-lang-0",
          "source_id": "source-parcel-lang-0",
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
        "query": "ParcelNest language in February?",
        "mode": "semantic",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.48501157504567094,
            "lexical_score": 0.0,
            "semantic_score": 0.48501157504567094,
            "result": {
              "status": "ok",
              "value": "NestJS",
              "evidence": [
                {
                  "event_id": "parcel-framework-fix",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "NestJS",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-framework-fix",
                  "supersedes_event_id": "parcel-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-framework-0",
                "parcel-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "language",
            "score": 0.40961387824834405,
            "lexical_score": 0.0,
            "semantic_score": 0.40961387824834405,
            "result": {
              "status": "ok",
              "value": "TypeScript 5",
              "evidence": [
                {
                  "event_id": "parcel-lang-0",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "language",
                  "value": "TypeScript 5",
                  "event_type": "declare",
                  "observed_at": "2026-01-01T00:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-lang-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-lang-0",
                "parcel-lang-a",
                "parcel-lang-b"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.3585757736066858,
            "lexical_score": 0.0,
            "semantic_score": 0.3585757736066858,
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
      "rank": 2,
      "recalled_at_3": true,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "NestJS",
      "actual_source_ids": [
        "source-parcel-framework-fix"
      ],
      "citation_valid": 2,
      "citation_total": 2,
      "citation_checks": [
        {
          "event_id": "parcel-framework-fix",
          "source_id": "source-parcel-framework-fix",
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
        "mode": "semantic",
        "as_of": "2026-01-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.4523297365133492,
            "lexical_score": 0.0,
            "semantic_score": 0.4523297365133492,
            "result": {
              "status": "ok",
              "value": "NestJS",
              "evidence": [
                {
                  "event_id": "parcel-framework-fix",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "NestJS",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-framework-fix",
                  "supersedes_event_id": "parcel-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-framework-0",
                "parcel-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.426348821906947,
            "lexical_score": 0.0,
            "semantic_score": 0.426348821906947,
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
          },
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.416897001766443,
            "lexical_score": 0.0,
            "semantic_score": 0.416897001766443,
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
          }
        ],
        "provider": "repomind_semantic"
      }
    }
  },
  {
    "provider": "repomind_semantic",
    "question_id": "dev-12",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "ParcelNest",
        "text": "Which cache_service has ParcelNest adopted?",
        "as_of": "2026-07-01T23:59:59.999999Z",
        "known_at": null,
        "expected_key": null,
        "expected_status": "unknown",
        "expected_value": null,
        "expected_source_ids": [],
        "question_id": "dev-12",
        "category": "unknown"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "NestJS",
      "actual_source_ids": [
        "source-parcel-framework-fix"
      ],
      "citation_valid": 3,
      "citation_total": 3,
      "citation_checks": [
        {
          "event_id": "parcel-framework-fix",
          "source_id": "source-parcel-framework-fix",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-db-complete",
          "source_id": "source-parcel-db-complete",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-deployment-0",
          "source_id": "source-parcel-deployment-0",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "project_id": "ParcelNest",
        "query": "Which cache_service has ParcelNest adopted?",
        "mode": "semantic",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "fingerprint": "openai-compatible-59b516d961af2658c5ea6c0738e720a7b4299cfb418c1468e9a3cc6ecfb8cd7a",
        "indexed_documents": 5,
        "hits": [
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.5066053999157841,
            "lexical_score": 0.0,
            "semantic_score": 0.5066053999157841,
            "result": {
              "status": "ok",
              "value": "NestJS",
              "evidence": [
                {
                  "event_id": "parcel-framework-fix",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "NestJS",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-framework-fix",
                  "supersedes_event_id": "parcel-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-framework-0",
                "parcel-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.36859057290254554,
            "lexical_score": 0.0,
            "semantic_score": 0.36859057290254554,
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
          },
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.3499720402996169,
            "lexical_score": 0.0,
            "semantic_score": 0.3499720402996169,
            "result": {
              "status": "ok",
              "value": "Docker",
              "evidence": [
                {
                  "event_id": "parcel-deployment-0",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "deployment",
                  "value": "Docker",
                  "event_type": "declare",
                  "observed_at": "2026-02-01T00:00:00Z",
                  "effective_at": "2026-02-01T00:00:00Z",
                  "source_id": "source-parcel-deployment-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-deployment-0"
              ],
              "plan_event_ids": []
            }
          }
        ],
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
      "citation_valid": 3,
      "citation_total": 3,
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
        },
        {
          "event_id": "aster-deployment-0",
          "source_id": "source-aster-deployment-0",
          "valid": true,
          "problems": []
        }
      ],
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
        "min_cosine": 0.2,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-bdd4435550d2a88924c4b712ee984c511a9e62dda1c24904027aa9d87b1167b8",
        "hits": [
          {
            "subject": "worker",
            "predicate": "database",
            "score": 0.5109955818503609,
            "semantic_score": 0.5109955818503609,
            "lexical_score": 0.0,
            "backend_rank": 1,
            "backend_memory_id": "e0ce33fd-499d-4762-89c3-9c50d8cbceb8",
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
            "score": 0.49721257097356575,
            "semantic_score": 0.49721257097356575,
            "lexical_score": 0.0,
            "backend_rank": 2,
            "backend_memory_id": "e556cfe2-62bb-4593-b7ff-5ebeda689385",
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
          },
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.45232896108408027,
            "semantic_score": 0.45232896108408027,
            "lexical_score": 0.0,
            "backend_rank": 3,
            "backend_memory_id": "af3942cd-053b-45a4-8697-b4d0b11f3bb1",
            "result": {
              "status": "ok",
              "value": "Docker",
              "evidence": [
                {
                  "event_id": "aster-deployment-0",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "deployment",
                  "value": "Docker",
                  "event_type": "declare",
                  "observed_at": "2026-02-01T00:00:00Z",
                  "effective_at": "2026-02-01T00:00:00Z",
                  "source_id": "source-aster-deployment-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-deployment-0"
              ],
              "plan_event_ids": []
            }
          }
        ]
      }
    }
  },
  {
    "provider": "mem0",
    "question_id": "dev-06",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "AsterDocs",
        "text": "AsterDocs 的 billing_service 使用哪个服务？",
        "as_of": "2026-07-01T23:59:59.999999Z",
        "known_at": null,
        "expected_key": null,
        "expected_status": "unknown",
        "expected_value": null,
        "expected_source_ids": [],
        "question_id": "dev-06",
        "category": "unknown"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "Docker",
      "actual_source_ids": [
        "source-aster-deployment-0"
      ],
      "citation_valid": 3,
      "citation_total": 3,
      "citation_checks": [
        {
          "event_id": "aster-deployment-0",
          "source_id": "source-aster-deployment-0",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "aster-framework-fix",
          "source_id": "source-aster-framework-fix",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "aster-db-complete",
          "source_id": "source-aster-db-complete",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "provider": "mem0",
        "project_id": "AsterDocs",
        "query": "AsterDocs 的 billing_service 使用哪个服务？",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-bdd4435550d2a88924c4b712ee984c511a9e62dda1c24904027aa9d87b1167b8",
        "hits": [
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.4027569520943083,
            "semantic_score": 0.4027569520943083,
            "lexical_score": 0.0,
            "backend_rank": 1,
            "backend_memory_id": "af3942cd-053b-45a4-8697-b4d0b11f3bb1",
            "result": {
              "status": "ok",
              "value": "Docker",
              "evidence": [
                {
                  "event_id": "aster-deployment-0",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "deployment",
                  "value": "Docker",
                  "event_type": "declare",
                  "observed_at": "2026-02-01T00:00:00Z",
                  "effective_at": "2026-02-01T00:00:00Z",
                  "source_id": "source-aster-deployment-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-deployment-0"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.39415818232375976,
            "semantic_score": 0.39415818232375976,
            "lexical_score": 0.0,
            "backend_rank": 2,
            "backend_memory_id": "214e684c-59be-43a3-8007-5dfcf25b4e9a",
            "result": {
              "status": "ok",
              "value": "FastAPI",
              "evidence": [
                {
                  "event_id": "aster-framework-fix",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "FastAPI",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-aster-framework-fix",
                  "supersedes_event_id": "aster-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "aster-framework-0",
                "aster-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.3917969868472841,
            "semantic_score": 0.3917969868472841,
            "lexical_score": 0.0,
            "backend_rank": 3,
            "backend_memory_id": "e556cfe2-62bb-4593-b7ff-5ebeda689385",
            "result": {
              "status": "ok",
              "value": "PostgreSQL",
              "evidence": [
                {
                  "event_id": "aster-db-complete",
                  "project_id": "AsterDocs",
                  "subject": "project",
                  "predicate": "database",
                  "value": "PostgreSQL",
                  "event_type": "complete",
                  "observed_at": "2026-04-05T10:00:00Z",
                  "effective_at": "2026-04-01T00:00:00Z",
                  "source_id": "source-aster-db-complete",
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
        ]
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
      "rank": 2,
      "recalled_at_3": true,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "NestJS",
      "actual_source_ids": [
        "source-parcel-framework-fix"
      ],
      "citation_valid": 3,
      "citation_total": 3,
      "citation_checks": [
        {
          "event_id": "parcel-framework-fix",
          "source_id": "source-parcel-framework-fix",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-lang-0",
          "source_id": "source-parcel-lang-0",
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
        "provider": "mem0",
        "project_id": "ParcelNest",
        "query": "ParcelNest language in February?",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-02-15T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-cc01ca3b517e01268a34a6872f685b9d56ef9d22805413ddd0c1725d6ed75029",
        "hits": [
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.48560242688798344,
            "semantic_score": 0.48560242688798344,
            "lexical_score": 0.0,
            "backend_rank": 1,
            "backend_memory_id": "ba105dec-ceb8-415b-a9af-6a39dcb752a8",
            "result": {
              "status": "ok",
              "value": "NestJS",
              "evidence": [
                {
                  "event_id": "parcel-framework-fix",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "NestJS",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-framework-fix",
                  "supersedes_event_id": "parcel-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-framework-0",
                "parcel-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "language",
            "score": 0.41435259512200456,
            "semantic_score": 0.41435259512200456,
            "lexical_score": 0.0,
            "backend_rank": 2,
            "backend_memory_id": "f9d13570-0eec-4f43-9ce4-b92cbe77d557",
            "result": {
              "status": "ok",
              "value": "TypeScript 5",
              "evidence": [
                {
                  "event_id": "parcel-lang-0",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "language",
                  "value": "TypeScript 5",
                  "event_type": "declare",
                  "observed_at": "2026-01-01T00:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-lang-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-lang-0",
                "parcel-lang-a",
                "parcel-lang-b"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.3621416531702474,
            "semantic_score": 0.3621416531702474,
            "lexical_score": 0.0,
            "backend_rank": 3,
            "backend_memory_id": "7dab5978-f1c5-4cf5-a352-dd64d8f930ae",
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
        ]
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
      "rank": 2,
      "recalled_at_3": true,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "NestJS",
      "actual_source_ids": [
        "source-parcel-framework-fix"
      ],
      "citation_valid": 2,
      "citation_total": 2,
      "citation_checks": [
        {
          "event_id": "parcel-framework-fix",
          "source_id": "source-parcel-framework-fix",
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
        "provider": "mem0",
        "project_id": "ParcelNest",
        "query": "ParcelNest 的 project database 在一月二十日是什么？",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-01-20T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-cc01ca3b517e01268a34a6872f685b9d56ef9d22805413ddd0c1725d6ed75029",
        "hits": [
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.45365345337693225,
            "semantic_score": 0.45365345337693225,
            "lexical_score": 0.0,
            "backend_rank": 1,
            "backend_memory_id": "ba105dec-ceb8-415b-a9af-6a39dcb752a8",
            "result": {
              "status": "ok",
              "value": "NestJS",
              "evidence": [
                {
                  "event_id": "parcel-framework-fix",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "NestJS",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-framework-fix",
                  "supersedes_event_id": "parcel-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-framework-0",
                "parcel-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.4287129185627336,
            "semantic_score": 0.4287129185627336,
            "lexical_score": 0.0,
            "backend_rank": 2,
            "backend_memory_id": "7dab5978-f1c5-4cf5-a352-dd64d8f930ae",
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
          },
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.4196905177113632,
            "semantic_score": 0.4196905177113632,
            "lexical_score": 0.0,
            "backend_rank": 3,
            "backend_memory_id": "8d956b76-f763-436b-bb8d-89364618d505",
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
          }
        ]
      }
    }
  },
  {
    "provider": "mem0",
    "question_id": "dev-12",
    "error_phase": null,
    "details": {
      "passed": false,
      "failure_stage": "retrieval",
      "error": null,
      "query": {
        "project_id": "ParcelNest",
        "text": "Which cache_service has ParcelNest adopted?",
        "as_of": "2026-07-01T23:59:59.999999Z",
        "known_at": null,
        "expected_key": null,
        "expected_status": "unknown",
        "expected_value": null,
        "expected_source_ids": [],
        "question_id": "dev-12",
        "category": "unknown"
      },
      "rank": null,
      "recalled_at_3": false,
      "top1_correct": false,
      "answer_correct": false,
      "sources_correct": false,
      "actual_status": "ok",
      "actual_value": "NestJS",
      "actual_source_ids": [
        "source-parcel-framework-fix"
      ],
      "citation_valid": 3,
      "citation_total": 3,
      "citation_checks": [
        {
          "event_id": "parcel-framework-fix",
          "source_id": "source-parcel-framework-fix",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-db-complete",
          "source_id": "source-parcel-db-complete",
          "valid": true,
          "problems": []
        },
        {
          "event_id": "parcel-deployment-0",
          "source_id": "source-parcel-deployment-0",
          "valid": true,
          "problems": []
        }
      ],
      "project_leakage": false,
      "leaked_event_ids": [],
      "schema_issues": [],
      "response": {
        "provider": "mem0",
        "project_id": "ParcelNest",
        "query": "Which cache_service has ParcelNest adopted?",
        "mode": "mem0_controlled_retrieval",
        "as_of": "2026-07-01T23:59:59.999999+00:00",
        "known_at": null,
        "top_k": 3,
        "min_cosine": 0.2,
        "indexed_documents": 5,
        "snapshot_id": "snapshot-cc01ca3b517e01268a34a6872f685b9d56ef9d22805413ddd0c1725d6ed75029",
        "hits": [
          {
            "subject": "project",
            "predicate": "framework",
            "score": 0.508895286057113,
            "semantic_score": 0.508895286057113,
            "lexical_score": 0.0,
            "backend_rank": 1,
            "backend_memory_id": "ba105dec-ceb8-415b-a9af-6a39dcb752a8",
            "result": {
              "status": "ok",
              "value": "NestJS",
              "evidence": [
                {
                  "event_id": "parcel-framework-fix",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "framework",
                  "value": "NestJS",
                  "event_type": "correct",
                  "observed_at": "2026-05-01T09:00:00Z",
                  "effective_at": "2026-01-01T00:00:00Z",
                  "source_id": "source-parcel-framework-fix",
                  "supersedes_event_id": "parcel-framework-0"
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-framework-0",
                "parcel-framework-fix"
              ],
              "plan_event_ids": []
            }
          },
          {
            "subject": "project",
            "predicate": "database",
            "score": 0.36950189212332596,
            "semantic_score": 0.36950189212332596,
            "lexical_score": 0.0,
            "backend_rank": 2,
            "backend_memory_id": "7dab5978-f1c5-4cf5-a352-dd64d8f930ae",
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
          },
          {
            "subject": "project",
            "predicate": "deployment",
            "score": 0.34736228473623754,
            "semantic_score": 0.34736228473623754,
            "lexical_score": 0.0,
            "backend_rank": 3,
            "backend_memory_id": "8d956b76-f763-436b-bb8d-89364618d505",
            "result": {
              "status": "ok",
              "value": "Docker",
              "evidence": [
                {
                  "event_id": "parcel-deployment-0",
                  "project_id": "ParcelNest",
                  "subject": "project",
                  "predicate": "deployment",
                  "value": "Docker",
                  "event_type": "declare",
                  "observed_at": "2026-02-01T00:00:00Z",
                  "effective_at": "2026-02-01T00:00:00Z",
                  "source_id": "source-parcel-deployment-0",
                  "supersedes_event_id": null
                }
              ],
              "reason": "latest_effective_fact",
              "considered_event_ids": [
                "parcel-deployment-0"
              ],
              "plan_event_ids": []
            }
          }
        ]
      }
    }
  }
]
```
