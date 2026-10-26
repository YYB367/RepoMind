# RepoMind

具备长期记忆与自我评测能力的 AI 开发助手。本轮版本 **V1.0 Memory MVP** 是离线结构化事件记忆 CLI：保留项目历史、区分计划和事实、按有效时间查询，并返回来源证据。未来 Agent 能力仅属于路线规划。

## 范围

已完成 P0 与 V1：领域校验、SQLite 账本、确定性状态解析、结构化检索、来源追溯和离线评测。实际验收：88 项测试通过，开发集 32/32，保留集首次 16/16，串项目 0 次。完整记录见 [V1 验收报告](reports/acceptance.md)。

本轮不调用 LLM 或 Embedding，不部署 Mem0、OpenViking、Langfuse，不实现 Web 前端、代码修改 Agent 或 Harness 自优化。

## 安装与运行

要求 Python 3.11+；已验证 Windows PowerShell、Python 3.12.14、Pydantic 2.14.1、pytest 9.1.1、SQLite 3.53.1。以下命令不需要激活脚本或改变 ExecutionPolicy。

```powershell
Set-Location 'D:\software\codex\2026-10-26\1-repomind-codex-md-2-repomind\outputs\RepoMind'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -e '.[dev]'
.\.venv\Scripts\repomind.exe import data/fixtures/conversations.jsonl
.\.venv\Scripts\repomind.exe query --project CampusRecruit --field database --as-of 2026-03-15
.\.venv\Scripts\repomind.exe query --project CampusRecruit --field database --as-of 2026-04-10
.\.venv\Scripts\repomind.exe eval --dataset data/dev/questions.jsonl --output reports/v1-dev.md
.\.venv\Scripts\repomind.exe eval --dataset data/holdout/questions.jsonl --output reports/v1-holdout.md
.\.venv\Scripts\python.exe -m pytest -q
```

3 月迁移计划不会替换实际数据库；4 月完成事件生效后更新。重复导入必须幂等。每次 query 可在新进程运行，使用同一 SQLite 文件。

本机 PATH 没有 `python`，验收实际使用 Codex 的本地解释器。若仍在本机，可用以下首条命令创建虚拟环境，然后执行上面剩余命令：

```powershell
& 'C:\Users\czx\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv
```

本次已安装并验证的环境位于交付目录之外，可立即运行：

```powershell
Set-Location 'D:\software\codex\2026-10-26\1-repomind-codex-md-2-repomind\outputs\RepoMind'
& '..\..\work\acceptance-venv\Scripts\repomind.exe' --help
& '..\..\work\acceptance-venv\Scripts\repomind.exe' import data/fixtures/conversations.jsonl
& '..\..\work\acceptance-venv\Scripts\repomind.exe' query --project CampusRecruit --field database --as-of 2026-04-10
```

本机受限会话的默认 pytest 临时目录不可访问；可将临时文件放入工作区。普通环境无需此调整：

```powershell
New-Item -ItemType Directory -Force '../../work/tmp' | Out-Null
$env:TEMP = (Resolve-Path '../../work/tmp').Path
$env:TMP = $env:TEMP
& '..\..\work\acceptance-venv\Scripts\python.exe' -m pytest -q --basetemp '../../work/pytest-manual'
```

`repomind` 与 `python -m repomind` 等价。`--db` 可放在命令前，或 import/query 子命令后；默认 `repomind.sqlite3` 位于当前目录。query 对不存在数据库报错，不会创建空账本。eval 使用独立临时数据库。

命令退出码：0 表示导入/查询成功或评测全部通过；1 表示评测有失败项；2 表示输入、配置或数据库错误。unknown/insufficient_evidence 是有效查询结果，退出码为 0。基线有预期失败，返回 1。

## 输入与时间语义

每行一个事件：event_id、project_id、subject、predicate、value、event_type、observed_at、source_id；effective_at 可省略，correct 额外要求 supersedes_event_id。所有事实和值为非空字符串，时间戳必须含时区。详见 [架构契约](docs/architecture.md)。

`as_of` 按事实有效时间查询；日期表示 UTC 当日末。`known_at` 可限制当时可见的观察记录。默认使用当前全部知识重建历史。计划不会自行成为事实，同生效时间的矛盾值返回 insufficient_evidence，无记录返回 unknown。

```powershell
.\.venv\Scripts\repomind.exe query --project CampusRecruit --field database --as-of 2026-04-01 --known-at 2026-04-01
.\.venv\Scripts\repomind.exe eval --baseline --dataset data/dev/questions.jsonl --output reports/baseline-dev.md
```

模型要求 ISO 时间戳显式带时区；不接受无时区时间或隐式 Unix 时间。仅 plan 允许 effective_at 晚于 observed_at。correct 必须指向同范围、同生效时间的旧事实；不抹去旧事件或后续已生效变更。支持批次乱序纠错，全部校验后原子提交。

## 设计与验收材料

- [架构和数据协议](docs/architecture.md)
- [需求与版本闸门](docs/requirements.md)
- [评测协议与防泄漏](docs/evaluation-plan.md)
- [架构决策 ADR](docs/decisions/)

固定 fixture 含60事件、3项目；48道题六类各8，32开发题和16保留题。题目包含67条结构化子查询，跨会话题按全部条件正确计分。保留集门槛至少13/16，本次达到16/16。文件 SHA-256 和冻结说明见 [data/manifest.json](data/manifest.json)。保留集已公开，下一版本需新增独立题。

| 验收项 | 结果 | 报告 |
|---|---|---|
| pytest | 88 passed / 0 failed | [JUnit XML](reports/pytest.xml) |
| 开发集 | 32/32，100% | [Markdown](reports/v1-dev.md) / [JSON](reports/v1-dev.json) |
| 保留集首次运行 | 16/16，100% | [Markdown](reports/v1-holdout.md) / [JSON](reports/v1-holdout.json) |
| 最后观察基线 | 开发22/32；保留8/16 | [开发](reports/baseline-dev.md) / [保留](reports/baseline-holdout.md) |
| 跨进程CLI演示 | 6个独立进程，导入/幂等/2月/3月/4月/未知项目通过 | [JSON](reports/cli-demo.json) |

规则系统两组共67条子查询：来源67/67合法，期望证据集合67/67匹配，未知信息8/8正确拒答，含冲突的拒答11/11，串项目0。小规模合成事件、精确字符串匹配和一次本地验收不能证明自然语言能力、真实开发收益或长期线上稳定性。未做大规模并发和压测；来源引用不认证外部文档真实性。

## 文件结构与变更

`src/repomind/domain/` 定义契约；`memory/` 定义导入、投影和检索；`adapters/sqlite.py` 保存原始事件及替代关系；`evaluation/` 隔离评分并生成双报告；`cli.py` 提供命令。`tests/` 含模型/持久化、状态、CLI、评分器和独立边界测试。`docs/`、`data/`、`reports/` 分别保留设计、固定输入和验收证据。

本轮从空工作区创建项目，原始规划文件副本保存于 `docs/planning/`。`D:\projects\RepoMind` 中原文件未修改。项目含本地 Git 历史；没有推送远程或部署。详细清单见 [CHANGELOG.md](CHANGELOG.md)。

## 后续版本

V1.1 仅规划自然语言事实提取与语义检索，必须单独验证抽取/检索错误。V1.2 平台对照、V2 Agent 和 V3 Harness 均未实施。V1 验收后停止。
