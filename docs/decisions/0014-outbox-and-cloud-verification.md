# 阶段目标：让 V1.2 平台同步可重放，并用服务侧读取证明云端状态

ADR0014；状态：接受；日期：2026-10-27；范围V1.2。

## 原方案与触发原因

V1.1本地报告无需网络ACK。V1.2引入异步SDK、trace/dataset/experiment多对象同步；SDKflush返回和对象ID可生成都不证明服务端已持久化。网络失败也不应触发重新付费运行模型。

## 替代方案比较

| 方案 | 收益 | 取舍 |
|---|---|---|
| 评测期间直接依赖云端成功 | 流程短 | 网络干扰质量计时，失败可能需重跑模型；不采用 |
| flush无异常即标verified | 容易实现 | 只有发送尝试，可能丢失或未可读；不采用 |
| 本地outbox+预计算结果重放+服务读回 | 结果可追踪，网络与模型解耦 | 采用；需要状态、重试和payload核对 |
| 声称stable trace ID保证exactly-once | 简化重试叙述 | span/item可能重复，不成立；不采用 |
| 只验dataset即宣称整个experiment成功 | 少一次读取 | 缺trace/item/score证据；不采用 |

## 决策与数据流

先完成本地评测并保存安全payload、稳定run/trace/experiment身份及内容hash，再同步。SDK experiment的task仅返回既有output，evaluator仅返回既有score；重放不再调用Embedding、LLM或resolver生成新答案。

trace通过OTEL，dataset写入、experiment/observation/score核验使用SDK5支持的新Public API。服务端读取须指定必要字段与时间范围，处理分页和IO反序列化，并比对内容，不仅查同名对象。

状态至少区分pending/local_only、sent_unverified、verified、retryable_failure。只有服务响应及必需对象读回核对完成，才能标cloud verified；SDK fake或localhost协议测试不等于真实cloud ACK。某些对象成功、其他失败时保留分对象回执。

## 重试与原理

提供至少一次投递，不承诺exactly-once。重试先查询已有对象，对已核对相同payload的对象跳过；不同payload或部分缺失保持诊断与待重试。稳定trace ID不能保证新span无重复，必须披露局限。

没有Langfuse配置时仅生成outbox，不猜host/地区，不开通服务。密钥不进payload、报告或错误原文；不自动上传.env或无关本地文件。平台错误保留本地结果，不改质量分数，也不把重放延迟当后端查询耗时。

## 影响、迁移与回滚

新增outbox与云端验证回执，但权威事实账本和旧报告不变。本地比较、SDK契约、live模型与cloud验证分别验收；缺cloud读取证据时明确尚未完成平台联通验证。

回滚可停用同步、保留outbox与receipt供后续处理；代码回滚不会自动删除外部dataset、实验或trace。清理不得静默删除云端数据。验证覆盖部分成功、flush后查无数据、payload不匹配、分页/延迟、重试跳过已ACK项，以及重放无新模型调用。

依据：2026-10-27查阅[Experiments via SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk)、[弃用API迁移](https://langfuse.com/faq/all/deprecated-api-migration)。本设计的ACK标准比单纯SDK flush更强；最终cloud状态须由真实回执证明。
