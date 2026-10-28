# 阶段目标：V1.2 用真实服务证据修正云端适配，保留失败并防止重复计量

状态：接受；2026-10-28。适用范围仅为 Langfuse 适配和验收，不修改检索金标、旧账本或 V1 时间规则。

## 实际发现

本地 SDK 协议测试通过后，首次真实云端读取返回 HTTP 400。安装的 SDK5.0.4 已明确说明 `parse_io_as_json=True` 被弃用，服务返回原始 JSON 字符串；本地模拟服务没有拒绝该参数，遗漏了这条约束。

第二个问题是用量字段：模型返回 `prompt_tokens=240,total_tokens=240`，直接作为两个自定义计数上传后，服务额外求和得出 `total=480`。这不能作为准确的云端 token 证据。最初 `live-dev-first` 的试验记录、失败回执和已上传对象保留，不用于最终云端用量汇总，不静默删除。

## 决策与原理

移除弃用参数，继续严格解析服务返回的 IO JSON。上传时将模型计数字段映射到 Langfuse 的 `input/output/total`；别名冲突拒绝处理，原始模型计数保留在 observation metadata。读取时核对标准字段及实际总数，不靠宽松“包含部分字段”宣称通过。服务从组成项推导 total 时，只接受与组成项之和一致的结果。

补充 `trace-sync --verify-only`：只读取既有 observations、scores 和 experiment items；缺失时保持未确认，不创建 dataset、不补发 spans 或 scores、不调用模型。它适用于异步数据已经发送、尚不可见的情况。正常同步仍保留至少一次重放能力，不能承诺 exactly-once。Experiment 的预计算回放使用 span，将原始 generation 计数作为 metadata，避免再次计入 generation 用量。

本地契约测试现在主动拒绝弃用参数，并覆盖原始 token 别名映射、错误 total 拒绝和只读模式不写入。真实读回证据另存在 reports/v1.2，不能用模拟测试替代云端验证。

云端联调还表明，逐题 flush 加立即多次轮询会放大网络等待，未必等到异步数据可见。改为先核对已有对象、让 SDK 批量发送缺失记录、统一 flush、再逐项读取。默认单轮读取；数据稍后可见时使用 `--verify-only`，不靠高频重复发送推进状态。中断前的 outbox/status journal 保留，后续继续核验同一身份。批量 flush 失败必须将受影响记录标为失败，不能标已确认。

## 取舍、兼容与回滚

只修改本地模拟以放宽读取、忽略 total、或把 flush 返回当作成功，都不能解决事实问题。直接修改已冻结的 outbox 会改变 payload hash、破坏审计，因此保留它并在适配器边界规范化。正式验收使用 `live-dev-cutoff-020` 与 `live-holdout-first` 的独立 trace/run 标识。

没有 SQLite schema 迁移；旧事件与 V1.1 配置保持兼容。`--verify-only` 是新增可选参数。停止平台同步即可回滚到本地报告；已创建的云端对象仍保留。如需清理应按明确 run 标识人工处理，不在回滚时自动删除。真实报告使用候选版本号；正式发布的版本号和云端适配修正不重新解释其检索输出。
