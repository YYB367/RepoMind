# V1 评测协议

状态：P0 预先规定的评分协议，2026-10-26。最终数据 manifest 与验收报告记录实际样本数、SHA-256 和运行命令。

## 数据与隔离

fixture 约60条事件、3个虚拟软件项目，包含多会话来源、计划/完成、延迟观察、纠错、同时间冲突、重复值和未知字段查询。48题分六类，每类8题：basic（基础事实）、temporal（时间推理）、state（更新与冲突）、cross_session（跨会话）、isolation（项目隔离）、unknown（未知与拒答）；manifest 固定这些分类名。

开发集32题用于实现检查；保留集16题在开发集和核心单元测试通过后用于首次发布验收。按项目和问题模板尽量隔离，保留集优先使用未用于调试的第三项目及组合变化。项目隔离题需要跨项目同名字段，因此不能声称所有题完全按项目互斥。

题目和标准答案由数据设计者按事件历史独立编写，禁止调用被测 resolver 生成标准答案。文件写入即冻结并计算 SHA-256；保留集交付后公开可复现，因此不再是未来版本的真正盲测集。实际划分：CampusRecruit、ShopLedger、BuildPilot 各20事件；BuildPilot 不进入开发题，保留题以该项目为主，含多项目隔离检查。开发中不读保留答案调规则；发生保留集失败须记录首次结果、根因和后续回归，不能宣称修复后仍是首次盲测。

每题包含稳定 ID、category、一个或多个结构化 query、预期 status/value 与 event/source 引用。跨会话题应验证多个会话中事件的联合条件或先后关系；多查询一题按全部查询正确才计分。V1 不解析题目自然语言。

## 系统与基线

被测系统：对隔离新 SQLite 导入固定 fixture 后运行 MemoryRetriever。每次评测不复用用户数据库，不污染已有记忆。严格相同 fixture、问题集与时间语义。

负对照基线：精确相同作用域键下，选择 observed_at 最新的记录；只考虑观察截止和基本查询上限，故意不处理 event_type、effective_at、correct 替代或冲突。并列时采用稳定 ID 顺序以便复现。它说明“最后一条消息就是事实”会错在哪里；不是与 Mem0 的公平能力比较，也不能称为无记忆 Agent 基线。

只评估确定性规则；不伪造 Token 成本、Embedding Recall@K 或 Agent 任务成功率。

## 指标与评分

严格逐题通过要求：所有查询的 status、value 与标准答案一致，预期支持事件集合匹配；每条引用在 fixture 中存在、source_id 正确、作用域和时间合法。unknown 不应引用虚构事实；冲突必须引用矛盾事件。correct 的值证据引用纠正事件，审计轨迹可以另列被替代记录。

| 指标 | 定义 |
|---|---|
| 总准确率 | 严格通过题数 / 总题数 |
| 分类准确率 | 每类严格通过题数 / 该类题数；保留分子分母 |
| 未知信息处理率 | 预期 unknown 或 insufficient_evidence 的题目中正确拒答比例；同时报告各状态分母 |
| 项目串用次数 | 返回证据 project_id 与 query 项目不同的查询/引用计数，明确计数单位；值相同不自动推断串用 |
| 来源引用正确性 | 返回引用中 ID、来源、范围和时间均合法的比例；同时报告预期证据完整性，避免空引用获得满分 |
| 运行时间 | perf_counter 单调时钟测量；记录评分和查询范围，不声称跨硬件可直接比较 |

同时输出逐题实际结果、标准答案、通过项和失败项。错误阶段优先级：provenance（非法引用或跨项目证据）、retrieval（预期证据未进入 considered_event_ids）、resolution（状态/时间/值错误）、provenance（仅支持证据集合错误）。输入/fixture 无效属于 evaluation 配置错误，应非零退出，不能悄悄计为成功。

报告配置包含 RepoMind 版本、Python/SQLite 版本、策略名称、fixture/question 路径与 SHA-256、题数、运行时间、分割标记；耗时和报告生成时间属于非确定字段。保存 latest-observation 负对照报告和 rule-v1 报告，不能覆盖旧版本比较证据。

## 复现与发布

PowerShell 命令在 README 中按实际 CLI 校准，预期路径：

```powershell
python -m pytest -q
repomind eval --dataset data/dev/questions.jsonl --output reports/v1-dev.md
repomind eval --dataset data/holdout/questions.jsonl --output reports/v1-holdout.md
```

eval 自动生成同名 JSON。若 fixture 通过单独参数指定，两组必须使用相同事件文件。分别运行 rule-v1 与 baseline 便于归因。验收报告应列出实际命令、通过/失败数与报告路径。

单元测试先覆盖模型校验、批量回滚、纠错引用、幂等、UTC 边界、乱序导入、known_at、计划、同时间冲突、跨项目与来源；CLI 子进程证明持久化。评分器需用人为构造错误结果验证错误引用和项目串用可被发现，避免只测试被测实现自身。

发布门槛为核心测试全部通过、串用0次、保留集至少13/16题，其他指标完整披露。16题规模小，合成数据和精确字符串查询不能证明真实开发收益、自然语言理解或生产长期稳定性。V1.1 前应新增独立语料和提取/检索分阶段评价，不能直接复用公开保留集声称泛化。


