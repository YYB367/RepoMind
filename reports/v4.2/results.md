# 阶段目标

V4.2 independently test pilot-nominated strategies and keep reference unless the original gate is met

## 开发集与两轮保留成绩

| 阶段 | 策略 | 严格完成 | 代码通过 | 请求 | 输入 Token | 输出 Token | 总 Token |
|---|---|---:|---:|---:|---:|---:|---:|
| 开发 | reference | 2/3 | 2/3 | 16 | 39,635 | 1,708 | 41,343 |
| 开发 | focused-evidence | 2/3 | 2/3 | 16 | 36,393 | 2,048 | 38,441 |
| 开发 | focused-evidence-compact | 2/3 | 2/3 | 17 | 37,432 | 1,784 | 39,216 |
| 保留第 1 轮 | reference | 3/4 | 4/4 | 20 | 48,860 | 5,304 | 54,164 |
| 保留第 1 轮 | focused-evidence | 4/4 | 4/4 | 21 | 43,487 | 4,691 | 48,178 |
| 保留第 2 轮 | reference | 2/4 | 3/4 | 22 | 51,963 | 5,535 | 57,498 |
| 保留第 2 轮 | focused-evidence | 4/4 | 4/4 | 22 | 47,471 | 5,009 | 52,480 |

## 门槛判定

锁定候选：focused-evidence。开发判定：no_threshold_gain。
- 第 1 轮：strict_completion_gain；总 Token 节省 11.05%；严格完成不降=True，代码通过不降=True。
- 第 2 轮：strict_completion_gain；总 Token 节省 8.73%；严格完成不降=True，代码通过不降=True。

支持晋升：False。实验推荐：reference。日常默认仍为 reference。

实际请求 134 次。输入 305,241、输出 26,079、合计 331,320 Token。金额未知。

失败试验 6 项，详见 failures.json；完整首次请求与工具轨迹见 live-trials.jsonl。

Controlled, author-constructed RepoMind-derived helper tasks; two rounds reuse the same four new holdout tasks. This is not third-party blind testing or production/Codex effectiveness proof.

网页/新会话的既有验证见 V4.1，本轮没有新增 Codex 会话，也没有把参考动作回放当模型收益。
