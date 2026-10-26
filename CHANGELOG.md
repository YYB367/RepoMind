# RepoMind 1.0.0 — 2026-10-26

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
