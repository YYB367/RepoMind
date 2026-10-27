# 阶段目标：独立验证 V1.1 提取、找键和端到端行为

冻结日期：2026-10-27。这里的标准答案由人工设计，不使用RepoMind extractor/resolver结果作oracle。录制提取响应是人工编写的test double，并非真实LLM录制；`real_model_quality=false`表示这些回放资产本身不能证明真实语言理解质量。

## 数据组成

| 文件 | 内容 |
|---|---|
| seed-events.jsonl | 3个新项目各3条基础事实，共9条；纠错只指向这些稳定ID |
| gold-events.jsonl | 9条seed加20条人工期望事实，共29条；用于跳过提取的检索单阶段输入 |
| dev/cases.jsonl | ProjectOrion、MarketMesh的12个开发case，共16条查询 |
| holdout/cases.jsonl | 仅TaskHarbor的6个保留case，共8条查询 |
| extraction-responses.jsonl | 18条人工回放响应，按完整来源envelope的content_hash索引 |
| recorded-vectors.json | 55条8维人工理想向量：31个文档输入hash、24个查询输入hash；仅测管线合同 |
| manifest.json | 计数、划分声明、文件SHA-256与协议说明 |

每个case含来源、人工expected_facts和1至2条查询。gold生效时间全部显式给出；部分回放候选effective_at=null，用于验证默认到observed_at。每条引文均是来源原文的精确片段。gold事件ID采用synthetic前缀，与产品生成ID无关，评分应比较完整事实字段、来源与引用，不要求两种ID算法相同。

## 执行语义

同一split的来源全部导入后再评估该split查询，不能逐case即时评估；查询可关联另一来源中的完成、纠错和冲突。检索单阶段使用gold-events.jsonl，不经LLM提取；输入可以包含所有项目，但必须先按query项目及known_at过滤，保留项目隔离检查。

SourceMessage.content_hash是完整可信envelope（project_id、source_id、observed_at、text）的规范化JSON哈希。标准答案独立手写；提取回放查找键只调用该契约的标准化/哈希方法，没有调用产品extractor、retriever或resolver生成标准答案。observed_at统一UTC序列，字符串文本不另加换行。

## 覆盖与限制

覆盖计划/完成、迟到有效时间、纠错seed、同刻冲突、中文/英文问法、未采纳事实拒答、另一个项目无记录、known_at历史、同来源多事实和跨来源状态。开发与保留来源项目隔离，但共享规则类型与常见字段名，不能声称模板完全独立。

题量小、文本短，且多数查询保留canonical字段词作为明确信号。这适合初步错误归因，不能代表真实仓库自然语言覆盖率。Embedding回放由单独协议资产提供；人工toy向量只能测工程排名路径，不能当真实语义检索效果。

保留集在开发验证后首次打开；保留文件及标准答案不得为迎合程序输出而修改。首次结果与修复后结果分别记录。未来公开后需追加新的独立保留数据，不能重复宣称本数据仍是盲测。

## 人工理想向量的用途与防误读

recorded-vectors.json声明kind=recorded_test_double，指纹为recorded:v1.1-hand-authored-key-vectors-not-a-model。每个predicate分配独立one-hot维度；查询在资产制作时按人工expected_key选择相同维度，未知键使用额外维度，与所有文档相似度为0。因此它故意提供理想排序信号，只用于检查向量缓存、快照、混合排名和最终规则连接，不衡量真实模型理解、语义质量或泛化能力。

该文件覆盖gold事件与人工提取回放产生的actual事件两种文档hash，以及每条查询的known_at观察快照。生成脚本只用产品Extractor和build_documents枚举待嵌入输入；没有用它们生成、调整标准答案，原5份冻结JSONL逐字节保持不变。gold与actual的事件ID排序可能改变文档输入，因此两种hash均单独覆盖。

产品运行时只接收精确文本hash查找表，不接收gold expected_key；任何未录制文本必须报错，不允许通过相似文本猜向量。这里记录24个查询hash不等于执行了保留集搜索评测；资产生成仅验证完整查找、维度、未知向量正交及未知文本拒绝，不运行产品搜索验收，也不调用远程服务。
