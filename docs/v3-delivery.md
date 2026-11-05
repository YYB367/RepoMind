# 阶段目标

完成 V3.0 的有限 Harness 改进闭环。用历史开发轨迹提名候选，在新开发任务上选择并锁定一项方案，再用隔离保留任务重复检验效果。

## 如何运行

需要 Python、Git 和 Docker Linux 引擎。Windows 本工作区可用 ../../work/v2-venv/Scripts/python.exe 执行命令，先设置 PYTHONPATH 为 src。若使用新环境，从源码根执行 python -m pip install -e '.[dev]'。已有的沙箱配置为 work/v2-sandbox.json。新机器先运行 python -m repomind agent-prepare 准备测试镜像。

~~~powershell
python -m repomind harness-tune --run-dir work/v3-local-replay
python -m repomind harness-validate --run-dir work/v3-local-replay
python -m repomind harness-tune --live --run-dir work/v3-local-live
python -m repomind harness-validate --live --run-dir work/v3-local-live
~~~

默认是人工动作回放。加 --live 使用当前 .env 的聊天配置。两阶段合计最多 168 次聊天请求，Docker 内公开测试另有预算。tune 用新目录，validate 使用同一目录读取开发报告和选择锁。部分失败证据保留在子目录。要独立复测，从新目录重跑两阶段。退出码反映工程完成状况，是否达到推荐条件读取 holdout.json 中的 promotion_supported。

## 技术原理和选择

V2 把完整会话送回模型，并让模型在固定回合内决定何时结束。V3 从 V2 开发集 r2 的 outbox 逐条核对摘要，重放写入事件与收尾状态，得到可审计的候选提名。比如最终公开与隐藏测试均通过却没有 finish 的轨迹，说明有必要检验收尾提醒。历史轨迹不会进入新任务提示。它们能说明已发生的行为，变更后的模型行为需重新运行验证。

两个受限开关分别控制写入正文的历史回显和基于公开状态的收尾提示。压缩保留实际执行的原动作及审计正文，模型可重新读取文件。收尾提示要求最后一次写入之后已有公开测试通过和非空 diff，它仍由模型决定何时 finish。枚举可拆开测单项和组合，并给候选相同的回合、工具和判题预算。对照始终要求模型正常结束、修改源码、通过两类最终测试。

开发报告、配置和代码通过 SHA-256 绑定到选择锁。validate 先校验选择锁，再打开保留输入。冻结材料分目录隔离。判题文件挂载在模型执行结束后的独立容器。选择标准优先严格完成数，再看代码通过数和实际 Token。推荐规则要求开发结果达门槛，两轮保留集都复现同类改善，且没有质量下降或模型身份差异。

另一种做法是开放式改写执行器，让模型产生任意策略。这会扩大搜索空间和安全面，也难以保证重复试验的预算。本阶段沿用 V2 工具白名单和容器，把优化限制在两个开关。选择和回放分别借鉴候选探测与历史反馈。详见 [ADR 0021](decisions/0021-finite-harness-and-independent-gate.md) · [Harness²](https://arxiv.org/abs/2610.14224) · [Dream-RSI](https://arxiv.org/abs/2609.14858)。

## 文件变更、兼容与回滚

- src/repomind/harness 保存轨迹复用、候选规则、评测和推荐门槛。agent/loop 增加两个默认关闭的选项。
- data/v3 含新编写的 SignalBox 仓库、3 道开发题和 4 道保留题、公开测试、独立判题、人工参考动作和冻结清单。
- CLI 增加 harness-tune 和 harness-validate。reports/v3 存放实际运行与回归证据，tests/test_harness.py 验证锁、历史和推荐条件。

无需迁移 SQLite、经验库或旧数据。选择结果只记录在实验目录中，既有 agent-bench 使用其原默认值。旧包与 v2.1.0 标记可用于回滚程序。

## 实际验收

平台全量 pytest **473 项通过**，包含 4 项真实 Docker 隔离测试。人工动作回放 28/28，通过工具、公开判题、隐藏判题和选择锁链路。回放期间聊天请求为零。实测镜像沿用 V2 的固定 Linux 镜像。[JUnit 记录](../reports/v3/pytest-platform.xml)

复用了 18 条 V2 开发轨迹，记录到 19 次成功写入和 2 次代码通过却未收尾的运行。首次开发集排序锁定 guided。原始协议和实现于 d0c1bd3 冻结，保留集实际运行前已持久化选择锁。

| 开发策略 | 严格完成 | 代码通过 | 请求 | 输入 Token | 输出 Token |
|---|---:|---:|---:|---:|---:|
| 原始流程 | 2/3 | 3/3 | 16 | 18,590 | 1,138 |
| 仅压缩 | 2/3 | 3/3 | 16 | 18,540 | 1,184 |
| 仅收尾提示 | 3/3 | 3/3 | 14 | 16,587 | 1,163 |
| 压缩加收尾提示 | 3/3 | 3/3 | 15 | 17,197 | 1,227 |

**guided 未通过预定的可复现改善门槛，推荐保留 reference。**

| 保留轮次 | 策略 | 严格完成 | 代码通过 | 请求 | 输入 Token | 输出 Token |
|---|---|---:|---:|---:|---:|---:|
| 1 | 原始流程 | 4/4 | 4/4 | 18 | 22,037 | 1,783 |
| 1 | 仅收尾提示 | 3/4 | 4/4 | 20 | 24,899 | 1,744 |
| 2 | 原始流程 | 4/4 | 4/4 | 18 | 22,570 | 1,835 |
| 2 | 仅收尾提示 | 4/4 | 4/4 | 16 | 19,372 | 1,740 |

第 1 轮严格完成为原始流程 4/4、候选 3/4，代码通过分别为 4/4、4/4。
第 2 轮严格完成为原始流程 4/4、候选 4/4，代码通过分别为 4/4、4/4。

候选在两轮保留集相对原始流程的输入加输出 Token 降幅依次为 -11.9%、13.5%。负数表示实际用量增加。判定原因依次为 quality_regression、token_saving_at_equal_or_better_quality。

合计真实 DeepSeek 调用 133 次，输入 159,792 Token，输出 11,814 Token。金额未核账。[开发结果](../reports/v3/live-dev.json) · [选择锁](../reports/v3/live-selection-lock.json) · [保留结果](../reports/v3/live-holdout.json) · [逐试验记录](../reports/v3/live-trials.jsonl)。

## 尚待验证的范围

首轮 hold-samples 中，候选第 3、4 回合的输出分别遇到解析和动作校验错误。回合提醒挂在正常工具反馈之后，这两个回合没有发送提醒。第 6 回合才完成公开测试与 diff，模型没有剩余回合提交 finish。保留这份失败记录，V3 以预览包交付，正式版本的可复现改善验收仍待满足。

两轮保留集复用相同四道合成题，能观察运行波动。任务和金标由同一开发会话编写，真实项目上的泛化、跨模型稳定性和长期收益待验证。当前方案只依据公开工具状态提示收尾，隐藏判题保持独立。性能建议由实验报告给出，实际使用仍需显式选择策略。
