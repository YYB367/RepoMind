# 阶段目标：V1.1：分别验证有来源的事实提取、人工事件检索和端到端记忆回答

验证状态：`live_pipeline_measured`。真实提取与独立 Embedding 流水线已测量；完整发布仍需外部核心回归与独立保留集验收。

## 指标

| 阶段 / 指标 | 结果 | 分子 / 分母 |
|---|---:|---|
| 提取 Precision（完整事实） | 100.00% | 13 / 13 预测事实 |
| 提取 Recall（完整事实） | 100.00% | 13 / 13 标准事实 |
| 提取案例全对 | 100.00% | 12 / 12 案例 |
| 人工事件检索 Recall@3 | 100.00% | 14 / 14 有标准事实键的查询 |
| 人工事件 Top1 键命中 | 100.00% | 14 / 14 有标准事实键的查询 |
| 人工事件最终答案全对 | 100.00% | 16 / 16 查询 |
| 端到端最终答案全对 | 100.00% | 16 / 16 查询 |
| 端到端未知信息处理 | 100.00% | 3 / 3 预期 unknown 查询 |
| 原文引用与来源合法性（各阶段累计） | 100.00% | 41 / 41 检查 |
| 跨项目串用 | 0 | 含串用的查询数 |
| 全用例严格通过 | True | 每个提取案例 + 两条查询路径均全对 |
| 数值发布门槛 | True | 外部 pytest 与真实服务验证须另验 |
| 运行耗时 | 35.134132s | 含提取、导入、索引、查询和评分；不含报告写入 |

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

无失败案例。

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
  "implementation_sha256": "ed112d8593e32ec65c704b8946378afcdd842c892936109ede3b749b5f86e002",
  "repomind_installed_version": "1.1.0rc1",
  "pydantic_version": "2.14.1",
  "sqlite_version": "3.53.1",
  "extraction_provider": {
    "name": "deepseek:chat=deepseek-flash;embedding=unset;format=json_object",
    "fingerprint": "openai-compatible-83311ef5799a5777bac725539a1eb5747f747343282ef4efaf26301fe1e2e238",
    "request_count": 12,
    "usage": {
      "prompt_tokens": 18450,
      "completion_tokens": 1264,
      "total_tokens": 19714
    },
    "extraction_prompt_sha256": "a8ef170c9dd2cad7f265bbb891091d696e17e8ce99c7d8b24b289b2b634a267a",
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
      "prompt_tokens": 2080,
      "total_tokens": 2080
    },
    "extraction_prompt_sha256": "a8ef170c9dd2cad7f265bbb891091d696e17e8ce99c7d8b24b289b2b634a267a",
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
  "min_cosine": 0.55,
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
