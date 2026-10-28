# 阶段目标：在Windows本地复现V2样例代码Agent与三组对照

从RepoMind源码目录执行；本轮验收使用Python3.12、Docker Desktop Linux引擎和既有模型配置。只对自带ParcelKit副本执行，不把用户真实项目作为运行目标。V2.1/V3不在此命令范围内。

## 安装与准备

```powershell
Set-Location 'D:\software\codex\2026-10-26\1-repomind-codex-md-2-repomind\outputs\RepoMind'
python -m venv .venv-v2
.\.venv-v2\Scripts\python.exe -m pip install -e '.[dev,platform]'
$RepoMindExe = '.\.venv-v2\Scripts\repomind.exe'
```

无python PATH时，可使用本机已有解释器`C:\Users\czx\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`创建venv。仅本地Agent无需platform SDK；Langfuse和旧Mem0对照仍为可选依赖。精确复现本轮可先安装requirements-v2.lock再用--no-deps安装项目，锁文件对应Windows/Python3.12，不保证跨平台逐字节一致。

本工作区可直接使用已准备的`..\..\work\v12-venv\Scripts\python.exe -m repomind`配合`$env:PYTHONPATH='src'`运行开发源码；正式wheel安装验证另有报告。不要覆盖已有.env，DeepSeek和Langfuse继续读取原独立配置，容器不继承这些key。

启动本机Docker Desktop并选择Linux引擎后，显式构建可信测试镜像：

```powershell
& $RepoMindExe agent-prepare --output work/v2-sandbox.json
& $RepoMindExe agent-doctor --sandbox-config work/v2-sandbox.json
```

prepare只把docker/v2中的Dockerfile、锁定pytest依赖和可信测试入口送入构建，不发送根目录或.env。只有该准备阶段需要拉镜像/安装依赖；模型run_tests固定禁网、不可拉镜像，只使用配置中的本地不可变image ID。Docker不可用时停止，不回退到宿主pytest。

镜像构建来源和实际image ID随报告保存；以后相同配方重建的ID不保证相同。严格对照需使用同一构建产物，并记录基础镜像digest和依赖锁。wheel本身不包含Docker镜像或样例数据，agent-prepare应在源码包根目录运行，或显式指定--project-root。

## 先跑动作回放

```powershell
& $RepoMindExe agent-bench --data-root data/v2-r2 --dataset data/v2-r2/dev/tasks.jsonl --provider replay --run-id replay-manual-001 --output reports/v2/replay-manual-001.json
```

人工参考动作三组相同，分数只说明工具/隔离/评分管线可工作，不代表真实模型准确率、成本或记忆收益。原data/v2保留以复现首轮数据；正式示例使用只补明公开契约的data/v2-r2，隐藏判题未改。

## 真实开发集和首次保留集

```powershell
& $RepoMindExe config
& $RepoMindExe agent-bench --data-root data/v2-r2 --dataset data/v2-r2/dev/tasks.jsonl --provider live --run-id live-manual-001 --output reports/v2/live-manual-001.json
```

默认baseline/memory/enhanced三组、6轮/3次公开测试/20动作。可用--variants明确选择子组，--max-turns和--max-test-runs改变预算；比较时必须对所有组保持一致，不在holdout观察结果后改预算。

dev验证后固定预算、提示词和镜像，再首次执行holdout：

```powershell
& $RepoMindExe agent-bench --data-root data/v2-r2 --dataset data/v2-r2/holdout/tasks.jsonl --provider live --run-id holdout-manual-001 --output reports/v2/holdout-manual-001.json
```

每次测量用新的run-id和报告路径，默认状态位于work/v2-runs。程序拒绝覆盖已有状态/报告或将运行状态写入冻结数据。每项已完成任务立即写outbox，任务仓库、Git diff和经验库保留供审计；中断不会自动重跑模型，也不自动复用未完成测量来冒充完整run。

## 查看结果与同步

JSON保留逐任务工具、源码diff、公开/隐藏判题、停止状态、经验来源和实际usage；Markdown汇总成功率/重试率。compare/agent-bench退出0表示测量无工程错误，不保证所有质量题通过。源码断言失败、代码资源超限或提前退出都不能被算通过；宿主引擎/清理故障另外记工程错误。

```powershell
& $RepoMindExe trace-sync both --outbox reports/v2/live-manual-001.traces.jsonl --dataset-name RepoMind-V2-Dev --receipt reports/v2/live-manual-001-cloud.json
& $RepoMindExe trace-sync both --verify-only --outbox reports/v2/live-manual-001.traces.jsonl --dataset-name RepoMind-V2-Dev --receipt reports/v2/live-manual-001-readback.json
```

同步只回放既有合成结果；不再运行模型或pytest。sent_unconfirmed保留待核验，不当作成功。相同outbox/dataset-name可只读确认，避免异步延迟时重复上传。费用默认未知；--pricing只接受明确价卡估算，不代表账单。

## 测试与边界

```powershell
$env:REPOMIND_TEST_AGENT_IMAGE = (Get-Content work/v2-sandbox.json | ConvertFrom-Json).image
.\.venv-v2\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp work/pytest-v2
```

未设置测试镜像时，4项真实Docker隔离测试会明确跳过。API/key只在宿主适配器使用；工具不支持shell、网络、任意pytest参数、隐藏测试读取或修改真实项目。代码仍共享容器内Python判题进程，不能把本轮当成抗恶意作弊的通用代码评测服务。详细原理、取舍和回滚见v2-technologies.md及ADR0016–0019。
