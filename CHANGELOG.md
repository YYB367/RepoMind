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
