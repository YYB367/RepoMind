# 阶段目标：交付 V1.1 Intelligent Memory，理解技术原因并验证真实模型链路

日期：2026-10-27，Asia/Shanghai。目标是把自然语言来源转成有引文的结构化候选，用词法/向量混合检索找到属性，再由原V1内核处理项目、时间、计划、完成和纠错。**本轮已完成V1.1验收，停止于V1.1；未开发V1.2、V2或V3。**

最终发布版本为1.1.0。真实模型开发/保留评测在1.1.0rc1候选上完成，评测后产品代码仅更新发布版本元数据与交付材料；1.1.0另通过311项测试和完整CLI示例。各真实报告保留当时的软件版本、实现hash、Prompt hash、输入hash、模型配置及用量，没有把旧报告改写为新版本运行。

## 已完成什么

自然语言JSONL来源包含project_id/source_id/observed_at/text。可信范围由调用者封装，模型不能改项目或来源。DeepSeek生成候选；Pydantic检查字段、时间、事件类型和纠错引用，精确引文必须在原文中存在。默认生成候选与审核工件，显式apply才将来源、事件和引文一起原子写入。原始结构化import/query/eval继续可用。

检索按项目与known_at先过滤历史，再以完整属性键建立文档。命中属性后加载全部相关事件，交给V1 resolver投影as_of状态；不会因为计划更相似就把计划当成实际状态。无候选返回空hits，已有属性但无有效事实返回unknown，同刻未消解冲突返回insufficient_evidence。

重复来源内容不变时复用账本中的提取事件和引文，不再调用随机模型；同一批次的重复来源也只提取一次。同source_id内容变化会拒绝，重新提取或修订来源应使用新的source_id，以保留审计轨迹。

## 为什么用这些技术，基本原理是什么

| 技术 | 采用原因 | 原理与本项目落点 |
|---|---|---|
| DeepSeek JSON Output | 用户选择的自然语言提取服务 | 将会话映射到受约束的JSON候选；使用非思考Chat接口、json_object和max_tokens，不让模型直接写数据库 |
| Pydantic与原文引文检查 | JSON合法仍可能有错字段、错时间和错范围 | 按类型和领域约束验证；可信envelope覆盖范围/来源/观察时间，引文必须是原文片段。两者仍不能证明模型理解必然正确 |
| SQLite事件账本 | 保留跨进程历史，并让写入全部成功或全部失败 | 事务一起提交来源、事件、引文；纠错通过显式替代边表达，旧记录不覆盖 |
| Qwen Embedding与余弦 | 找到问法与属性文档之间的相关性 | 文本变成1024维向量，按向量方向接近程度排名；相似度不是概率，也不能代替事件有效性判定 |
| 词法与RRF融合 | 同时保留明确字段词和语义候选 | 两路分别排名，以1/(60+名次)相加；避免直接混加不同量纲分数。过滤余弦的步骤发生在融合前 |
| 模型指纹与SHA-256 | 防止旧文档、旧模型、不同时间快照混用 | 缓存绑定项目/属性/模型/维度策略/文档hash；known_at改变或新增事件导致文档变化时，明确重新index |
| 标准库HTTP、argparse、pytest | 保持本地MVP依赖与复现成本可控 | 使用同一服务的HTTP协议，不必为两个非流式接口引入SDK；CLI输出结构化结果，测试分别定位协议、提取、检索、解析错误 |

详细公式、逐步例子、替代方案和局限见 [技术原理说明](../../docs/v1.1-technologies.md)。SDK不是另一种模型：用户给出的dashscope.TextEmbedding.call本质上也在发送HTTP请求。本轮用适配器直接构造等价请求；以后若需要更多协议能力，应重新评估SDK，而不是认为SDK永远没有必要。

## 技术变更为什么发生

| 原方案 | 触发原因与最终方案 | 影响、取舍和回退 |
|---|---|---|
| V1只接结构化事件 | V1.1要处理会话，因此增加可审核候选入口，仍由V1内核决事实 | 模型可能误解内容，所以不跳过校验；旧入口保留。[ADR0005](../../docs/decisions/0005-constrained-extraction.md) |
| 只按精确属性查询 | 相似旧事件可能抢答案，改为先检索属性键再解析完整历史 | 排名与事实判定分开，避免向量分数覆盖计划/时间规则。[ADR0006](../../docs/decisions/0006-hybrid-key-retrieval.md) |
| SQLite schema1 | 来源全文、提取引文、向量缓存需要持久化，事务增量迁移到schema2 | 原events不改。旧V1 binary不识别schema2，升级前关闭连接并备份，回滚恢复备份；不能只改PRAGMA版本。[ADR0007](../../docs/decisions/0007-additive-schema-and-staged-evaluation.md) |
| 假定所有服务支持strict JSON Schema | DeepSeek Chat文档支持json_object，改为该协议并保留本地Pydantic | 不静默用正则容错；拒绝无效候选，错误报告仅给字段位置/类型，不回显输入或密钥。[ADR0008](../../docs/decisions/0008-deepseek-compatible-output.md) |
| 按用户最初SDK示例接DashScope native | 用户实际.env地址为compatible-mode；native路径在该地址返回404，因此匹配OpenAI-compatible协议 | 保留用户地址、模型、Key和区域选择，只切协议；首404报告保留。原生适配也有本地协议测试，但当前真实配置使用兼容协议。[ADR0009](../../docs/decisions/0009-dashscope-embedding.md) |
| 通用余弦门槛0.2 | 真实dev中无记录属性与其它文档仍有0.44–0.52相似度；Qwen profile显式校准为0.55 | 仅用dev调参，API/离线默认仍0.2，可CLI覆盖。较高门槛可能降低纯语义弱匹配召回，不能宣称适合所有模型/数据。发布评分门槛不变。[ADR0010](../../docs/decisions/0010-dev-calibration-and-diagnostics.md) |

同时补充了完整的合法JSON正例和安全字段诊断；没有加入隐藏重试。首次真实dev失败报告保留，标准答案、题目和发布评分门槛均未修改。

固定数据SHA-256是字节校验。Windows自动把CRLF转LF会使语义相同文件的hash变化，因此对已冻结的V1.1数据关闭Git换行转换，保留原始字节。实际从干净Git归档验证9个冻结文件，全部hash匹配，见reproducibility-check.json。没有通过重写金标内容来追平结果。

## 实际配置与运行

已验证Windows PowerShell、Python3.12.14、Pydantic2.14.1、pytest9.1.1、SQLite3.53.1。没有新增SDK、NumPy、向量数据库或外部平台依赖。

- 提取：deepseek-flash，https://api.deepseek.com，json_object，非思考模式，输出上限2048tokens。
- 向量：qwen3.7-text-embedding-flash，用户实际地址https://maas.qianwenaiapi.com/compatible-mode/v1，1024维。
- 检索：hybrid，Top3，真实服务验收min_cosine=0.55。录制回放使用人工理想向量与0.2，不拿它证明模型效果。
- 独立Key分别保存在项目根.env；配置值不进入源码、报告或压缩包。config命令只显示是否已配置，不显示Key。

```powershell
Set-Location 'D:\software\codex\2026-10-26\1-repomind-codex-md-2-repomind\outputs\RepoMind'
$RepoMindExe = '..\..\work\acceptance-venv\Scripts\repomind.exe'
& $RepoMindExe config
& $RepoMindExe ingest examples/v1.1-sources.jsonl --output work/candidates.jsonl
& $RepoMindExe --db work/demo.sqlite3 ingest examples/v1.1-sources.jsonl --output work/candidates.jsonl --apply
& $RepoMindExe --db work/demo.sqlite3 index --project CampusDemo
& $RepoMindExe --db work/demo.sqlite3 search --project CampusDemo --text 'Which database is in use?' --as-of 2026-04-10 --mode hybrid
```

完整安装、结构化兼容入口、source回查和错误码见 [README](../../README.md)。受限沙箱的网络首次被WinError10013阻止；在授权网络执行环境中真实请求成功。普通本机运行不需要为本项目关闭证书验证或配置高权限工具。

## 实际测试与分阶段指标

最终实际执行：

```powershell
& '..\..\work\acceptance-venv\Scripts\python.exe' -m pytest -q --basetemp '../../work/pytest-v11-release' --tb=short --junitxml reports/v1.1/pytest.xml
```

**311 passed，0 failed，0 errors，0 skipped，22.20秒。** 覆盖原V1规则、schema迁移、来源/事件/引文原子回滚、重复来源复用、可信范围/观察时间绑定、协议与错误处理、缓存失效与快照、向量维度、RRF、配置文件、CLI、独立评分器和冻结数据身份。

另外构建并实际安装了dist/repomind-1.1.0-py3-none-any.whl，从项目目录外确认版本1.1.0、模块来自独立环境site-packages、全部命令帮助可用。package-check.json核对安装代码与交付源码的实现hash一致；pip check无损坏依赖。wheel没有依赖源码PYTHONPATH运行。

| 真实指标 | 首次dev（调整前） | 校准后dev | 首次holdout |
|---|---:|---:|---:|
| 提取案例全对 | 11/12 | 12/12 | 6/6 |
| 完整事实Precision | 12/12，100% | 13/13，100% | 7/7，100% |
| 完整事实Recall | 12/13，92.31% | 13/13，100% | 7/7，100% |
| 人工事件Recall@3 | 14/14 | 14/14 | 7/7 |
| 人工事件查询全对 | 14/16 | 16/16 | 8/8 |
| 端到端查询全对 | 13/16，81.25% | 16/16，100% | 8/8，100% |
| 无相关属性拒答 | 0/2 | 2/2 | 1/1 |
| unknown正确处理 | 1/3 | 3/3 | 1/1 |
| 来源/引文合法检查 | 104/104 | 41/41 | 23/23 |
| 跨项目串用 | 0 | 0 | 0 |
| 耗时，秒 | 34.805 | 35.134 | 17.435 |

来源合法性100%不代表回答一定正确：第一次dev的无关属性引用来自真实账本，但回答了错误的问题。分阶段指标和失败案例正是用于区分“引用存在”“召回相关”“状态解析正确”。

数值门槛在评测实现时固定：提取P>=0.90、R>=0.85；人工事件Recall@3>=0.90；端到端>=0.80；来源合法性100%；串项目0。all_passed要求每个案例和查询都正确，比数值门槛严格。初次dev满足数值门槛但all_passed=false，仍继续修复并披露失败，没有把它描述成全过。

保留集在dev校准和核心回归稳定后首次执行，未依据其结果改规则。新数据3个虚拟项目、9条seed、20条新增人工标准事实、18条来源案例、24条查询；holdout使用未出现在dev来源/问题中的TaskHarbor。保留集发布后不再作为未来版本的真正盲测集。

| 其它验证 | 结果与文件 |
|---|---|
| 离线人工响应/向量回放 | dev12/12案例、16/16查询；holdout6/6案例、8/8查询；offline-*.json/md明确test double |
| V1旧规则评测回归 | dev32/32、旧holdout16/16，v1-*-regression.json/md；旧报告未覆盖 |
| 真实CLI演示 | live-cli-demo.json：6个独立进程验证apply、3月MySQL、Qwen索引、4月PostgreSQL、原文回查、重复来源0新增并复用缓存 |
| 原生DashScope协议 | 25项localhost测试；20条拆批、document/query角色与错误验证。当前用户真实服务用兼容协议，不能把这些本地测试称原生端点live成功 |
| Git分发复现 | reproducibility-check.json：9个固定输入在Git归档内hash全部一致 |

## 真实调用用量

以下是服务实际返回的usage，不估算费用，不等同于账单；request_count为适配器调用计数，失败且无usage时不伪造token数。不同模型tokenizer不同，不用跨模型token数比较成本。

| 运行 | DeepSeek请求/总tokens | Qwen请求/总tokens |
|---|---:|---:|
| 首次dev | 12 / 16494 | 42 / 2037 |
| 校准后dev | 12 / 19714 | 42 / 2080 |
| 首次holdout | 6 / 10027 | 20 / 1126 |

另有连通性与CLI示例调用，单列在相应记录中；本表不是全会话账单汇总。DeepSeek smoke返回789tokens，Qwen兼容smoke返回61tokens。没有购买服务或增加云部署。

## 尚未解决的限制

当前没有阻塞V1.1发布的已知缺陷，但下列限制仍需保留：

- 真实评测只有18条合成来源、24查询。很多题带显式属性名，不能据此证明混合检索优于词法检索，或证明广泛自然语言泛化。
- 0.55仅为当前Qwen模型、当前dev的保守配置。换模型、文档编码或语料需要重新校准；弱语义匹配可能拒绝召回，不能把余弦分数当正确概率。
- 模型输出仍可能变化或不合规。错误被拒绝和记录，不保证每次生成都正确；精确引文不等于事实语义必然正确。
- 没有大规模性能、长期运行、远程权限、备份恢复演练或全部Python版本矩阵验证。来源审计不认证外部来源真实性。
- 属性历史全部进入文档和提取上下文；长历史仍受请求大小、模型上下文和服务批量限制。原生DashScope可按20条分批；通用兼容路径受所配置服务的单次输入上限约束。
- SQLite升级后不能直接用旧V1 binary读取；需要升级前备份才能回滚数据库。本轮验证的是增量迁移和原数据保持。
- 使用模型会向配置的服务发送所选来源/同项目上下文或索引文档。当前演示和评测只使用合成数据。
- 不实现自由生成式问答、外部平台、代码执行Agent或自优化；仅返回检索到的属性及其可验证状态。

## 文件变更和下一步

本轮新增intelligence/的来源封装、提取、配置、回放、DashScope适配、索引检索模块，扩展SQLite与CLI，新增分阶段评测、固定数据、测试、目标/技术说明及ADR0005–0010。详细清单见 [CHANGELOG](../../CHANGELOG.md)。

V1.2后续只建议评估Langfuse/Experiment与Mem0同集对照，继续保留本轮基线；本轮没有接入或开发这些能力。交付文档的“目标→原因/原理→变更取舍→运行/验收→限制”要求已写入AGENTS.md，供之后的阶段持续遵守。
