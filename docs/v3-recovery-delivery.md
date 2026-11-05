# 阶段目标

补齐 V3.0 的协议错误恢复提醒，并用新任务验证可复现改善。原路线图到 V3.0，本轮按该阶段的验收补强处理。

## 运行方法

在源码目录运行。需要 Python、Git 和可用的 Docker Linux 引擎。新环境先安装项目并运行 python -m repomind agent-prepare。本工作区可继续使用 ../../work/v2-venv/Scripts/python.exe，在运行源码前把 PYTHONPATH 设为 src。

~~~powershell
$common = @('--suite','data/v3-recovery','--history','reports/v3/live-trials.jsonl')
python -m repomind harness-tune @common --run-dir work/v3-recovery-local
python -m repomind harness-validate @common --run-dir work/v3-recovery-local
~~~

默认用人工动作回放。两条命令同时加 --live 并改用新的目录，可使用 .env 中的既有聊天配置复测，聊天请求合计上限为 150。开发阶段写出选择锁，验证阶段读取同一目录。holdout.json 的 promotion_supported 字段给出验收决定。已有试验目录保留原证据。

## 技术原理、变更与兼容

模型输出按 JSON 与动作 schema 解析。即使解析失败，该请求也已消耗一个回合。之前这类失败会绕过收尾提示。本轮让正常工具回复与可恢复协议错误复用反馈组装，预算提醒从已消耗回合数推导，并与协议诊断一起传给模型。

例如旧的 hold-samples 在第 4 回合触发动作校验错误。此时实际只剩两轮，新候选会提示在准备就绪时合并公开测试与 diff，留一轮提交 finish。提示仍依据公开状态，判题与停止权限维持独立。网络错误继续立即终止。对比过静态系统提示、增加回合和自动收尾，选择动态提醒能保留原预算和严格评分定义。[ADR 0022](decisions/0022-preserve-guidance-on-protocol-error.md)

历史证据通过摘要核对，提取原试验的一处漏发位置。新试验采用 RelayBox，开发题与保留题拥有各自的工作副本和隐藏判题。开发阶段比较原始流程、错误恢复提示、错误恢复提示加写入压缩；保留阶段只比较锁定候选与原始流程。两轮均须通过原推荐门槛。真实对照衡量候选整体表现，协议故障回归测试单独验证提醒是否送达。[补验计划](v3-recovery-plan.md)

## 文件变更、迁移和回滚

- agent/loop 复用反馈组装并增加默认关闭的恢复提醒开关。harness 新增历史漏发诊断和协议版本 2。
- data/v3-recovery 含新冻结的 3 道开发题、4 道保留题、公开及隐藏测试和人工动作。tests/test_harness_recovery.py 复现解析失败、动作校验失败和终止型网络错误。
- 原 V3 报告和 v2.1.0 发布标记继续作为历史参考。无需迁移数据库或配置。若要继续运行原实现的锁定试验，请使用原 V3 预览程序。

## 实际验收

全量 pytest **477 项通过**，包括 4 项真实 Docker 隔离测试。25 次人工动作回放通过。确定性故障测试对比旧策略和新策略的下一轮输入，确认恢复候选在校验失败且还剩两轮时发送提醒。[JUnit 报告](../reports/v3-recovery/pytest-platform.xml)

程序和新语料冻结在 598c7cb。开发阶段锁定 compact-guided-recovery。**恢复提醒加写入压缩未达到可复现改善门槛，实验保留原始流程。**

| 数据 | 策略 | 严格完成 | 代码通过 | 聊天请求 | 总 Token |
|---|---|---:|---:|---:|---:|
| 开发 | 原始流程 | 2/3 | 3/3 | 14 | 19,674 |
| 开发 | 恢复提醒 | 3/3 | 3/3 | 18 | 27,150 |
| 开发 | 恢复提醒加写入压缩 | 3/3 | 3/3 | 16 | 22,141 |
| 保留第 1 轮 | 原始流程 | 4/4 | 4/4 | 22 | 33,405 |
| 保留第 1 轮 | 恢复提醒加写入压缩 | 4/4 | 4/4 | 21 | 30,361 |
| 保留第 2 轮 | 原始流程 | 4/4 | 4/4 | 19 | 27,694 |
| 保留第 2 轮 | 恢复提醒加写入压缩 | 4/4 | 4/4 | 22 | 31,674 |

候选两轮相对原始流程的总 Token 降幅分别为 9.1%、-14.4%。负值表示使用量上升。开发判定为 strict_completion_gain，两轮保留判定为 no_threshold_gain、no_threshold_gain。

实际 DeepSeek 请求 132 次，输入 176,567 Token，输出 15,532 Token。逐轮记录中有 14 次可继续的协议诊断，其中 2 次携带控制器提醒。当前回合与公开工具状态决定是否该提醒，金额未核账。[开发结果](../reports/v3-recovery/live-dev.json) · [选择锁](../reports/v3-recovery/live-selection-lock.json) · [保留结果](../reports/v3-recovery/live-holdout.json) · [逐试验记录](../reports/v3-recovery/live-trials.jsonl)

## 尚待验证的范围

真实对照中，开发题 dev-batch 和第二轮保留题 hold-runs 都在第四回合出错后，于第五回合收到提示。两项候选运行随后完成并通过判题。两例可确认实际请求中包含提醒，无法单独估计提醒对完成率的贡献。

协议修复的回归证据可以重复获得。实际模型对照使用同一批四道合成保留题做两轮，尚需更广的任务与模型来验证泛化。新候选与原始流程的真实对照包含收尾提示的整体作用，提醒送达与最终完成率之间的关系需要更多试验才能分辨。

可复现改善仍待满足。以第二份 V3.0 预览包交付，原冻结分数保留。
