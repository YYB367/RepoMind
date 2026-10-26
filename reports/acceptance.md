# RepoMind P0 / V1 验收记录

验收日期：2026-10-26（Asia/Shanghai）。结论：**通过 V1 发布闸门，停在 V1.0**。

## 范围与架构

以 `docs/planning/RepoMind_Codex_执行提示词.md` 为主要依据，归档只作为背景。开始时 `D:\projects\RepoMind` 只有两份规划，本次工作区没有仓库、代码或未提交修改。完整项目交付于 `outputs/RepoMind`，原目录文档未修改。

P0 三份设计与四份 ADR 在业务实现前完成，并保留本地提交。参考研究实际核验了 Mem0 官方 ADD/SEARCH 文档、OpenViking README 和 Langfuse 评测文档；未安装平台、未审阅其运行源码，访问日期与限制已写进架构文档。

写入路径为 JSONL → Pydantic 校验 → 整批引用/幂等检查 → SQLite 原子提交。账本保存原始文本、事件/来源 ID、观察/生效时间和替代关系。查询按完整项目/主体/属性范围取候选，再由确定性解析器排除计划、应用纠错、投影有效事实。评测在独立临时数据库逐题执行，标准答案只交给评分器。

V1 包含结构化导入、持久化、幂等、计划/完成/纠错、双时间查询、冲突拒答、证据引用、CLI、固定数据和离线评分。不包含模型、Embedding、GUI、外部记忆平台、代码工具 Agent 或 Harness 优化。

## 实际环境与安装

Windows PowerShell；Python 3.12.14；Pydantic 2.14.1；pytest 9.1.1；SQLite 3.53.1。业务依赖仅 Pydantic；其余为标准库，pytest为测试依赖。精确依赖保存在 `requirements-dev.lock`。

PATH 未配置 Python。实际解释器为：

```text
C:\Users\czx\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

初步开发使用 `work/.venv`，最终验收使用另建、不继承系统site-packages的 `work/acceptance-venv`。依赖从预先下载的 wheel 安装，然后实际执行了：

```powershell
Set-Location 'D:\software\codex\2026-10-26\1-repomind-codex-md-2-repomind\outputs\RepoMind'
$PythonExe = '..\..\work\acceptance-venv\Scripts\python.exe'
$RepoMindExe = '..\..\work\acceptance-venv\Scripts\repomind.exe'
New-Item -ItemType Directory -Force '../../work/tmp' | Out-Null
$env:TEMP = (Resolve-Path '../../work/tmp').Path
$env:TMP = $env:TEMP
& $PythonExe -m pip install --no-index --no-build-isolation --find-links '../../work/wheels' -e '.[dev]'
& $PythonExe -m pip check
& $RepoMindExe --version
```

`pip check` 输出 `No broken requirements found.`，版本输出 `1.0.0`。普通联网环境的独立安装路径见 README，无需全局安装或 PowerShell 激活脚本。

另外已实际构建 `dist/repomind-1.0.0-py3-none-any.whl`，在同一独立虚拟环境中用普通wheel替换editable安装。随后从项目目录外确认模块来自该环境的site-packages，帮助命令及6个独立CLI进程演示通过；不依赖源码PYTHONPATH。该wheel随源代码压缩包提供。

## 测试与进程级演示

```powershell
& $PythonExe -m pytest -q --basetemp '../../work/pytest-acceptance' --tb=short --junitxml reports/pytest.xml
```

实际结果：**88 passed，0 failed，0 errors，0 skipped，9.66 秒**。JUnit XML 保存完整测试名与结果。

| 测试模块 | 通过 |
|---|---:|
| 领域模型与SQLite | 22 |
| 核心状态解析 | 5 |
| CLI及跨进程 | 9 |
| 独立评分器/报告 | 24 |
| 独立边界回归 | 28 |
| 合计 | 88 |

覆盖重启持久化、全部三维作用域隔离、历史时间、known_at、未来计划、完成生效、纠错链/分支、循环与悬空引用、乱序导入、重复ID与内容冲突、整批回滚、来源、同刻歧义、等值多证据、未知拒答、微秒/跨时区、输入错误与命令退出码。评分器另外注入错误值、错/伪造事件和来源、计划引用、项目串用、漏检与多条件部分失败，验证评分器确实会报错。

`reports/cli-demo.json` 另记录6个全新CLI进程：首次导入60条，重复导入0新增/60重复；2月数据库MySQL，3月计划期仍MySQL，4月10日PostgreSQL；无记录项目返回unknown。各次返回0，事实答案均包含event_id/source_id。没有共享进程内记忆。

## 固定评测与结果

数据先独立编写并固定 SHA-256，未调用被测系统生成标准答案。60事件、3项目；48题，六类各8；开发32/保留16。BuildPilot未进入开发题。代码实现、核心与独立评分测试、开发集通过后，保留集首次运行 **16/16**；未依据保留集结果修改规则或答案。

```powershell
& $RepoMindExe eval --dataset data/dev/questions.jsonl --output reports/v1-dev.md
& $RepoMindExe eval --dataset data/holdout/questions.jsonl --output reports/v1-holdout.md
& $RepoMindExe eval --baseline --dataset data/dev/questions.jsonl --output reports/baseline-dev.md
& $RepoMindExe eval --baseline --dataset data/holdout/questions.jsonl --output reports/baseline-holdout.md
```

每次生成同名JSON和Markdown。规则系统退出0；负对照因存在预期失败退出1，不代表测试命令崩溃。

| 指标 | V1开发 | V1保留首次 | 基线开发 | 基线保留 |
|---|---:|---:|---:|---:|
| 严格题目准确率 | 32/32，100% | 16/16，100% | 22/32，68.75% | 8/16，50% |
| 结构化子查询数 | 43 | 24 | 43 | 24 |
| 未知信息正确处理 | 5/5 | 3/3 | 4/5 | 3/3 |
| 拒答正确（未知+冲突） | 6/6 | 5/5 | 4/6 | 3/5 |
| 来源引用合法性 | 42/42 | 25/25 | 34/39 | 15/19 |
| 预期证据集合匹配 | 43/43 | 24/24 | 33/43 | 15/24 |
| 项目串用查询数 | 0 | 0 | 0 | 0 |
| 时间（秒） | 0.045803 | 0.042209 | 0.044557 | 0.041311 |

评测时间包含输入校验、临时账本导入、查询与评分，排除报告写盘；不包含CLI进程启动。不表示大数据或跨机器性能。

| 类别 | V1开发 | V1保留 | 基线开发 | 基线保留 |
|---|---:|---:|---:|---:|
| basic | 6/6 | 2/2 | 6/6 | 2/2 |
| temporal | 5/5 | 3/3 | 2/5 | 0/3 |
| state | 5/5 | 3/3 | 2/5 | 1/3 |
| cross_session | 6/6 | 2/2 | 4/6 | 0/2 |
| isolation | 5/5 | 3/3 | 4/5 | 2/3 |
| unknown | 5/5 | 3/3 | 4/5 | 3/3 |

严格正确要求一题所有子查询的status/value、证据集合和引用合法性全部正确。基线只取同范围最后观察记录，忽略计划/生效时间/纠错/冲突，作为负对照；不是Mem0或真实无记忆Agent。基线18道失败题的逐条原因和retrieval/resolution/provenance阶段保留在其报告中；V1失败列表为空。

## 修复记录与尚未解决的限制

首次模型/导入测试出现12通过、10个setup错误，原因是沙箱无法访问系统 `pytest-of-czx` 临时目录。改用工作区临时目录后22项通过，后续最终88项全部通过。

独立审查发现极端年份带偏移时间转UTC可能溢出，新增两个回归用例曾失败；模型已将OverflowError转为可诊断ValueError。回归与CLI验证通过，现返回错误JSON及退出2，不再输出traceback。

**当前无已知阻塞性缺陷。** 以下限制尚未验证或属于明确边界：

- 16题保留集、合成事件、共享规则内核，统计说服力有限；不能证明自然语言理解、真实开发收益或线上长期稳定性。
- 保留集已公开，后续版本需要新增独立题，不能重复使用本次公开题声称盲测泛化。
- 仅精确字符串和值；不做自然语言提取、语义检索、别名或单位推断。
- 只验收本机Python3.12.14，未运行所有声明支持的Python版本矩阵；未做大规模性能、多进程写入压力、备份恢复或远程权限验证。
- 每次导入在内存中验证账本，按单事实键加载历史，适合本轮小规模本地MVP。
- 来源是输入记录的可追溯引用，不等于外部真实性认证；SQLite不是多租户安全边界。
- 实际事实事件不能预先登记未来生效状态，未来日期只允许plan；不支持删除/撤回或自动取消计划。
- Python未加入PATH，但README提供当前可用解释器/环境路径。临时目录权限限制已有工作区替代路径。

## 下一版本建议（仅规划）

V1.1 可在现有事件契约之前增加自然语言候选事实提取，再独立评测提取错误与检索错误；加入Embedding/混合检索时继续保留项目隔离、时间投影和来源契约。先建立新保留集和V1规则基线。此次未实施V1.1、V1.2、V2或V3，也未部署或推送远程。

文件清单见 `CHANGELOG.md`；运行方法见 `README.md`；开发与验收证据保留在本地Git历史和本目录双格式报告。
