# 阶段目标：V2.0：用隔离代码工具完成样例任务，测量当前记忆与时序/经验增强的实际作用

运行 `live-holdout-first`；模式 `live`。

| 方案 | 任务成功 | 重试率 | 实际模型请求 | 输入token | 输出token | 工程错误 |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 1/4 | 0.0% | 22 | 31126 | 1902 | 0 |
| enhanced | 1/4 | 0.0% | 23 | 33176 | 2263 | 0 |
| memory | 1/4 | 0.0% | 22 | 31936 | 1833 | 0 |

## 解释范围

- replay对三组使用同一人工参考补丁，仅验工程管线，不测模型质量或记忆收益。
- baseline无记忆；memory读取当前事实；enhanced使用任务双时间并读取同run、同项目的此前成功经验。两项增强绑在一起，不能分别归因。
- 公开测试供Agent修复；隐藏测试在Agent停止后才执行，结果不反馈给该任务模型；保护不等于抵御故意伪造判题。
- 任务是合成业务代码样例，作者与实现者同会话；不是生产仓库/SWE-bench或独立盲测。样本少，不预设记忆必胜。
- Docker隔离宿主能力；镜像/路径/资源配置和实际测试另见JSON，不声称防御内核漏洞。
- Token只取实际响应，价卡缺失时货币费用未知；Langfuse只回放既有结果。

## 失败任务

```json
[
  {
    "variant": "baseline",
    "task_id": "hold-01",
    "agent_status": "finished",
    "error_type": null,
    "infrastructure_error": false,
    "public_passed": true,
    "hidden_passed": false
  },
  {
    "variant": "baseline",
    "task_id": "hold-02",
    "agent_status": "turn_budget_exhausted",
    "error_type": null,
    "infrastructure_error": false,
    "public_passed": true,
    "hidden_passed": true
  },
  {
    "variant": "baseline",
    "task_id": "hold-04",
    "agent_status": "finished",
    "error_type": null,
    "infrastructure_error": false,
    "public_passed": true,
    "hidden_passed": false
  },
  {
    "variant": "enhanced",
    "task_id": "hold-01",
    "agent_status": "finished",
    "error_type": null,
    "infrastructure_error": false,
    "public_passed": true,
    "hidden_passed": false
  },
  {
    "variant": "enhanced",
    "task_id": "hold-02",
    "agent_status": "turn_budget_exhausted",
    "error_type": null,
    "infrastructure_error": false,
    "public_passed": true,
    "hidden_passed": true
  },
  {
    "variant": "enhanced",
    "task_id": "hold-04",
    "agent_status": "turn_budget_exhausted",
    "error_type": null,
    "infrastructure_error": false,
    "public_passed": true,
    "hidden_passed": true
  },
  {
    "variant": "memory",
    "task_id": "hold-01",
    "agent_status": "turn_budget_exhausted",
    "error_type": null,
    "infrastructure_error": false,
    "public_passed": true,
    "hidden_passed": false
  },
  {
    "variant": "memory",
    "task_id": "hold-03",
    "agent_status": "finished",
    "error_type": null,
    "infrastructure_error": false,
    "public_passed": true,
    "hidden_passed": false
  },
  {
    "variant": "memory",
    "task_id": "hold-04",
    "agent_status": "turn_budget_exhausted",
    "error_type": null,
    "infrastructure_error": false,
    "public_passed": true,
    "hidden_passed": true
  }
]
```

## 配置

```json
{
  "provider_mode": "live",
  "dataset": "D:\\software\\codex\\2026-10-26\\1-repomind-codex-md-2-repomind\\outputs\\RepoMind\\data\\v2-r2\\holdout\\tasks.jsonl",
  "dataset_sha256": "4b7f7a23facce3564ebaf126a0a7e290b5615e11a74d9282e157c29707137785",
  "manifest_sha256": "6a2440ce14254b4ca56be71601926cd4d722e4e9c3c9ca81a55912c412165905",
  "implementation_sha256": "cc8e154a951fe01cd9685f84d33755ca909e7cec90fb2ca8c69e58dc58224337",
  "prompt_sha256": "372326b299594d252b7d54e7d6e3a0197dead417f40dc5772f2d7760deb61b01",
  "task_ids": [
    "hold-01",
    "hold-02",
    "hold-03",
    "hold-04"
  ],
  "budget": {
    "max_turns": 6,
    "max_test_runs": 3,
    "max_actions": 20,
    "max_context_chars": 24000
  },
  "seed": 0,
  "provider_order": [
    "baseline",
    "enhanced",
    "memory"
  ],
  "sandbox": {
    "backend": "docker_linux",
    "image_id": "sha256:58bf401e43e491ddc5999990162a01148ff6fcb836fe056781183eed03c5434d",
    "engine_version": "29.5.3",
    "network": "none",
    "root_filesystem": "read-only",
    "project_mount": "read-only",
    "user": "65532:65532",
    "capabilities": "ALL dropped",
    "no_new_privileges": true,
    "memory_mb": 256,
    "cpus": 1,
    "pids_limit": 64,
    "timeout_seconds": 25,
    "max_output_bytes": 65536,
    "host_code_fallback": false,
    "security_claim": "host capability isolation; not a hostile-code anti-cheating service or kernel-vulnerability guarantee"
  },
  "price_card_sha256": null,
  "experience_policy": "earlier successful tasks in same project and same run only; same-category preferred, latest project fallback; no cross-split history",
  "primary_comparison": "baseline vs memory vs combined temporal/experience enhanced; same initial code and tool budget"
}
```
