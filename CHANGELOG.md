# 阶段目标

RepoMind V3.0 Self-improving Harness，2026-11-05。交付历史轨迹提名、开发排序、候选锁和独立重复验证。

- 新增 V3 SignalBox 合成任务、harness-tune 与 harness-validate。
- guided 未通过预定的可复现改善门槛，推荐保留 reference。 首轮全量回归 473 项通过，真实模型运行和回放独立记录。

---

# 阶段目标

RepoMind V2.1 Context Engineering，2026-11-05。增加项目文档预算选择、OpenViking 分层读取和三组固定条件对照。

- 新增 context-select 和 context-bench，支持直接加载、向量检索和目录分层。
- 新增两档预算与冻结评测输入。首次保留集在 1800 字节下，分层与向量均为 8/8，分层少用 900 个回答输入 Token。640 字节下，分层为 5/8，向量为 7/8。
- 首轮平台测试通过 465 项，Docker 重启后补测 4 项全部通过。OpenViking 0.4.21 独立服务的两项目三层读取通过。
- 部署、技术变更及验收证据见 docs/v2.1-delivery.md 和 ADR 0020。

---

# 阶段目标：RepoMind V2.0 Developer Agent — 2026-10-28

交付2.0.0：有限JSON动作、限定文件/Git工具、Docker禁网只读限额执行、独立判题、成功任务经验。工程465项测试通过，基础442通过/23跳过；真实云端30条Trace、6个Experiment核验完成。没有实施V2.1/V3。

- 新增agent/、docker/v2、10个ParcelKit任务及三组真实对照；原命令和事件schema保留。
- 原dev严格完成2/6、3/6、5/6；r2澄清既有异常契约后为1/6、4/6、6/6。隐藏金标不变，前后不能全归因于系统提升。
- 首次holdout严格完成均1/4，未证明增益；代码验收2/4、2/4、3/4，另列预算停止和规格限制，不重写主分数。
- 只复制manifest登记文件，额外.env不进入模型副本；路径/链接/凭证/受保护文件和资源限额实测。
- developer_task参与预计算实验；export不再次计为模型调用，异步可见用只读核验。
- 所有真实调用、缓存子集和失败均保留，费用未知；详见docs/v2-delivery.md及ADR0016–0019。

以下历史版本保留原语境。

---

# 阶段目标：RepoMind V1.2 Evaluation Platform — 2026-10-28

本阶段增加公平MemoryProvider对照、实际usage/延迟与可选价卡估算，以及Langfuse trace/dataset/experiment的outbox与服务读回核验。1.2.0平台工程验收完成：426项测试通过，真实云端核对80条trace和8个experiment；真实dev质量限制仍保留。完整结果见docs/v1.2-delivery.md和reports/v1.2，不沿用V1.1历史数字作为本轮成绩。

## V1.2 新增/修改

- `docs/v1.2-stage-plan.md`、`docs/v1.2-technologies.md`、ADR0011–0015：SDK5/OTEL、受控Mem0公共配置桥、公平测量、usage/价卡和云端ACK设计，以及真实云端契约修复。
- `src/repomind/comparison/`：no_memory、repomind_semantic、repomind_hybrid、mem0受控profile；共享V1事实规则，主后端比较限定semantic与Mem0。
- `comparison/mem0.py`：infer=False、项目/known_at快照、本地Qdrant/history、Embedding回环桥、遥测/目录/可选模型控制、状态与资源关闭。
- `comparison/telemetry.py`、`pricing.py`：实际请求/usage和输入/向量hash、可选明确价卡估算；默认费用null。
- `src/repomind/platform/`：安全trace契约、单写者JSONL outbox与receipt，Langfuse5现代OTEL/experiment写入与新API读回核对。
- `src/repomind/cli.py`：新增compare与trace-sync，保留V1/V1.1命令；compare运行完成和质量分数分开，trace-sync仅cloud_verified完整时成功。
- `data/v1.2/`：3新项目、30事件、12dev/8holdout、44条6维人工理想向量、UTF-8 LF冻结manifest；未改旧版金标。
- `pyproject.toml`的可选platform extra：Langfuse5.0.4、mem0ai2.2.1、qdrant-client1.20.0；基础依赖继续轻量，平台延迟import。
- `README.md`、`docs/v1.2-usage.md`、`docs/v1.2-delivery.md`、`price-card.example.json`：安装、配置、对照、同步、费用缺失和回滚说明。价格示例为CNY空models，未包含真实报价。
- 新比较/桥接/测量/价卡/outbox/平台SDK/CLI测试：平台426 passed，基础407 passed/19 skipped。真实dev最终语义7/12、混合8/12、Mem0受控7/12；首次真实holdout三组有记忆方案均8/8。旧门槛失败、校准和云端初次失败均留档。
- 云端读取移除弃用参数，token别名转input/output/total防重复求和；SDK批量flush后核验，并支持--verify-only只读确认。没有为同步重跑模型，货币费用维持未知。

V1/V1.1代码入口、冻结数据、报告和历史标签保留。本轮不实现V2代码Agent、OpenViking或Harness优化，不推送远程或部署平台服务器。以下旧版本记录保留其当时语境。

---

# 阶段目标：RepoMind 1.1.0 Intelligent Memory — 2026-10-27

本阶段在V1的时间/来源内核上增加自然语言候选提取、独立Embedding与混合检索、分阶段评测。技术原因、原理、变更取舍与迁移说明见docs/v1.1-technologies.md及ADR0005–0010；完整结果见reports/v1.1/acceptance.md。

## V1.1 新增/修改

- `AGENTS.md`、`docs/delivery-standard.md`：保存用户持续要求，交付先列阶段目标，再解释原理、选择理由和变更。
- `docs/v1.1-stage-plan.md`、`docs/v1.1-technologies.md`：实施契约、原理、公式、比较和局限。
- `docs/decisions/0005`–`0010`：提取、检索、schema2、DeepSeek差异、Qwen原生/兼容协议、开发集校准。
- `src/repomind/intelligence/models.py`：可信来源封装、候选及来源绑定。
- `intelligence/providers.py`：受限HTTP、DeepSeek/OpenAI兼容输出、独立Embedding、实际usage和安全诊断。
- `intelligence/dashscope.py`：原生DashScope向量协议及独立配置工厂。
- `intelligence/extraction.py`：引文、纠错、时间和稳定事件ID。
- `intelligence/ingestion.py`：来源读取、可审核候选、已存来源/批次重复复用。
- `intelligence/config.py`：字面.env读取、安全状态与显式检索门槛。
- `intelligence/search.py`：属性文档、快照缓存、词法/余弦/RRF与完整V1解析。
- `intelligence/replay.py`：明确标记为测试替身的精确hash向量回放。
- `src/repomind/adapters/sqlite.py`：保留events，增量新增来源、引文、向量缓存，原子写入与范围读取。
- `src/repomind/cli.py`：新增config/ingest/index/search/source/eval-intelligence；保留原import/query/eval。
- `src/repomind/evaluation/intelligent.py`：提取、人工事件检索、端到端三路径独立评分与失败归因。
- `data/v1.1/`：3项目、9seed、29gold事件、12/6案例、16/8查询、人工回放及冻结manifest。
- `examples/v1.1-sources.jsonl`：可直接运行的合成示例。
- 新增提取、Provider、索引、DashScope协议、集成、评测、来源幂等、回放与数据身份测试，最终共311项通过。
- `reports/v1.1/`：初始失败、校准后真实dev、首次真实/离线holdout、V1回归、311项JUnit、CLI演示和分发复现。
- `README.md`、`.env.example`、`.gitignore`、`.gitattributes`、`pyproject.toml`及包版本：运行/配置、密钥排除、冻结字节保持和1.1.0发布。

本轮真实Qwen采用用户实际compatible-mode端点，模型仍qwen3.7-text-embedding-flash；未把Key写入交付物。V1.2及之后未实施；旧V1数据、报告和压缩包保留。

---

# RepoMind 1.0.0 — 2026-10-26（历史记录）

本轮完成 P0 与 V1 Memory MVP。起始工作区为空；全部产品文件为新增，原始规划文件未修改。

## P0

- `docs/architecture.md`：模块、ADD/SEARCH 流程、事件/查询契约、双时间、显式纠错、研究来源。
- `docs/requirements.md`：需求、非目标和版本闸门。
- `docs/evaluation-plan.md`：固定题、开发/保留隔离、严格评分、基线与复现。
- `docs/decisions/0001-no-llm-in-v1.md`：V1 不调用模型。
- `docs/decisions/0002-sqlite-persistence.md`：本地事务持久化。
- `docs/decisions/0003-append-only-bitemporal-events.md`：历史保留和双时间。
- `docs/decisions/0004-local-cli-no-platforms.md`：argparse、不部署复杂服务。
- `docs/planning/`：用户两份原始规划的副本。

## V1 实现

- `pyproject.toml`：Python 3.11+ 包、Pydantic 依赖、pytest 开发依赖和 CLI 入口。
- `requirements-dev.lock`：本次验收环境的精确依赖版本。
- `src/repomind/domain/models.py`：不可变领域模型、字段/时区/有效时间校验。
- `src/repomind/memory/base.py`：最小存储协议。
- `src/repomind/memory/store.py`：JSONL 诊断、重复键拒绝、纠错引用校验。
- `src/repomind/adapters/sqlite.py`：原始事件账本、schema 版本、原子导入、幂等和精确范围读取。
- `src/repomind/memory/resolver.py`：计划排除、有效时间投影、替代链、同刻冲突与拒答。
- `src/repomind/memory/retriever.py`：范围检索与解析连接。
- `src/repomind/cli.py`、`__main__.py`：import/query/eval/help、JSON 输出和退出码。
- `src/repomind/evaluation/metrics.py`：严格答案/证据/来源评分与错误阶段。
- `src/repomind/evaluation/runner.py`：隔离数据库、独立负对照、JSON/Markdown 报告、输入 SHA-256。
- 各 Python 包的 `__init__.py`。

## 数据、测试与交付

- `data/fixtures/conversations.jsonl`：60条模拟事件；3个项目各20条。
- `data/dev/questions.jsonl`、`data/holdout/questions.jsonl`：32/16题；六类各8道。
- `data/manifest.json`、`data/README.md`：冻结校验值、字段和隔离限制。
- `tests/test_core.py`：22例领域与持久化校验。
- `tests/test_resolver.py`：5例核心状态/历史/来源测试。
- `tests/test_cli.py`：9例CLI与跨进程验收。
- `tests/test_evaluation.py`：24例独立评分器和报告测试。
- `tests/test_adversarial.py`：28例独立边界回归。
- `reports/v1-dev.{md,json}`、`v1-holdout.{md,json}`：规则系统验收。
- `reports/baseline-dev.{md,json}`、`baseline-holdout.{md,json}`：简单负对照与失败明细。
- `reports/pytest.xml`、`cli-demo.json`、`acceptance.md`：测试、进程级演示和总验收。
- `README.md`、`.gitignore`、`.gitattributes`：运行说明、生成物忽略、LF 数据字节稳定策略。

未实现 V1.1、V1.2、V2、V2.1 或 V3；没有远程推送、云部署或服务购买。
