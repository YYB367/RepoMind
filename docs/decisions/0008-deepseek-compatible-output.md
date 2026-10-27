# 阶段目标：让 V1.1 正确适配 DeepSeek，而不假定所有兼容服务都支持相同能力

ADR 0008；状态：接受；日期：2026-10-27；范围：V1.1。本文补充ADR0005的输出模式与ADR0006的provider边界。

## 原方案

初版计划在OpenAI兼容Chat Completions中统一使用strict JSON Schema，并用同类配置访问embeddings。它适合明确支持该接口的服务，但“兼容”不等于每个参数、输出约束和端点全部相同。

## 触发原因与核验

用户选择DeepSeek并将在项目根.env填写key。2026-10-27查阅的官方Chat Completions参考列出response_format为text或json_object，使用max_tokens；JSON Output指南要求提示中明确JSON，并指出可能出现空内容或截断。Thinking指南给出thinking开关，默认启用；本阶段抽取请求显式关闭。[Chat API](https://api-docs.deepseek.com/api/create-chat-completion/)、[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)、[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)。

该日官方模型页列出deepseek-flash与deepseek-v4-pro；本项目模型ID继续由.env显式选定，不写死旧名称，不自动升级模型。此处核验接口不等于已经验证账户权限、调用结果或价格。[官方模型页](https://api-docs.deepseek.com/quick_start/pricing/)。

本轮查阅的DeepSeek官方端点参考未给出embeddings契约，因此不假定聊天key可计算向量；这不是对服务未来能力的永久断言。

## 替代方案比较

| 方案 | 优点 | 代价与本次选择 |
|---|---|---|
| 强行发送OpenAI strict json_schema | 实现表面一致 | DeepSeek参考未列该模式，可能请求即失败；不采用 |
| DeepSeek JSON mode + 本地Pydantic | 符合已核验接口；本地维持明确契约 | 服务端只保证JSON形状的基础层，字段/业务错误由本地拒绝；采用 |
| 改用另一个支持strict的提取provider | 可在服务端约束schema | 用户已选择DeepSeek；保留配置能力，不自动换服务 |
| 新增Responses专用适配 | 可使用另一个官方接口面 | 当前只需单次抽取，Chat兼容边界较小，避免双协议维护；本轮不做 |
| 自动退回自由文本/正则修补 | 容易得到看似可用结果 | 失败不透明，可能悄悄写错事件；不采用 |

DeepSeek官方页面已有Responses入口；本轮不实现是工程范围选择，不能写成“DeepSeek没有Responses”。

## 决策与原理

显式provider模式决定请求：DeepSeek发送response_format=json_object、合适max_tokens、thinking disabled，提示中给出JSON字段约束；支持strict的OpenAI模式继续发送json_schema。不会因一个请求失败自动降级或切换provider。

JSON mode使内容可作为JSON解析，但不能确保字段完整、枚举正确或没有额外字段。Pydantic在本地检查结构，业务校验再检查项目范围、时间、纠错和精确引文。空内容、截断、无效JSON或校验失败均终止该批次，不apply，不隐藏重试。

chat与embedding的base URL、模型和key配置完全分离。只有DeepSeek聊天配置时，可真实验证提取与显式lexical搜索；Embedding混合检索需另一个已配置provider，或仅运行明确标记的离线协议回放，不能据此宣称向量语义质量已验证。

.env只是本地配置载体，不是秘密管理平台；必须被Git忽略。环境变量优先级和实际变量名以README/实现为准；报告只写安全配置和模型身份，绝不输出key。用户选择模型不等于确认其质量，需冻结数据做live测量。

## 取舍与影响

放弃“所有provider一律服务端strict”的假设，增加显式模式与协议分支。DeepSeek分支的结构错误风险更依赖本地验证；即使本地全过，事实误读仍需人工审核和提取评测。禁止把JSON mode宣传为服务端JSON Schema保证。

提取live与Embedding live可能在不同时间完成。报告应分别标明：工程回归、提取服务真实调用、lexical检索、Embedding语义验收。不能用其中一项完成代替整个V1.1效果证明。

## 迁移与回滚

本决策不改变events或schema2结构；它改变提取配置和请求/解析分支。已有候选必须保留实际provider/model/output_mode，不把历史工件改标签。切换回支持strict的provider只改变配置，并重新做协议/live验证；不自动重提取已入库事实。停用DeepSeek入口仍可使用V1结构化导入。完整数据库回退继续遵循ADR0007的备份方案。

## 验证

协议测试断言DeepSeek参数、空输出/截断/错误字段拒绝、key不泄露、不同provider配置不混用；离线响应标test double。取得.env配置后再保存真实调用与提取评测，当前设计本身不宣称live已通过。Embedding服务未配置时明确待完成，不伪造向量分数。
