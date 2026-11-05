# 阶段目标

V3.0 Self-improving Harness 使用历史轨迹提名有限候选，按开发结果锁定方案，再独立复测。新增 harness-tune 和 harness-validate。

guided 未通过预定的可复现改善门槛，推荐保留 reference。 全量 pytest 473 项通过，另有 28 次人工动作回放通过。技术原理、运行方法与完整证据见 [V3 交付说明](docs/v3-delivery.md)。

## V2.1 Context Engineering

V2.1 Context Engineering 为项目选取受预算约束的文档证据，并对照直接、向量和目录分层三种策略。新增命令 context-select 和 context-bench，支持本地语料和可选的 OpenViking 只读分层访问。

首次保留集在 1800 字节下，向量与本地分层均答对 8/8，分层少用约 28% 的回答输入 Token。640 字节下，向量为 7/8，分层为 5/8。运行方法、测试证据和技术原理见 [V2.1 交付说明](docs/v2.1-delivery.md)。

## V2.0 Developer Agent

RepoMind 从事实记忆发展到有限步样例代码 Agent，支持读取和修改限定源码、运行隔离 pytest、查看 Git diff、独立判题并记录成功经验。

**2.0.0工程验收完成，效果结论保留。** 465项平台测试通过，基础环境442通过/23跳过；30条Trace和6个Experiment已经真实云端读回。首次holdout三组完整流程均1/4，未证明增强记忆提升完成率；单独代码验收为baseline2/4、memory2/4、enhanced3/4。10个任务为合成样例，不是生产或SWE-bench结论。

完整结果、文件变化、契约修订和问题见[V2交付说明](docs/v2-delivery.md)、[机器证据](reports/v2/acceptance.json)。[技术原理](docs/v2-technologies.md)解释工具链、容器和记忆数据流；[运行说明](docs/v2-usage.md)提供完整PowerShell命令。

## 核心技术为什么这样选

| 技术 | 原因与原理 |
|---|---|
| Python＋Pydantic | 复用旧内核；JSON动作通过schema和权限校验后才执行 |
| 有限动作循环 | 6回合/3次公开测试/20动作/24K字符，状态与停止可解释，不给模型shell |
| Docker Linux | 进程/网络/挂载隔离与资源限额；禁网、非root、只读，不继承宿主key |
| manifest与文件白名单 | 只复制登记源码，不把额外.env或Git配置带入任务；拒绝路径/链接越界 |
| V1 resolver＋SQLite | 解释计划/完成/纠错；最终验收成功后才存经验，按项目与顺序检索 |
| DeepSeek JSON接口 | 重用已实测传输和usage，模型建议不能改变工具权限 |
| Langfuse/outbox | 同步预计算结果，读回输出/评分/用量再确认，不重跑模型 |

三组定义为无历史、当前快照、任务双时间加此前成功经验。时序和经验绑在一起，不能分别归因。显式键路由降低语义召回混杂，没有修好V1.2语义检索弱点。

## 安装和准备

本轮验收为Windows、Python3.12及Docker Desktop Linux引擎。测试镜像只含Python和固定pytest依赖；key留在根.env，不能复制进镜像。

~~~powershell
Set-Location 'D:/software/codex/2026-10-26/1-repomind-codex-md-2-repomind/outputs/RepoMind'
python -m venv .venv-v2
./.venv-v2/Scripts/python.exe -m pip install -r requirements-v2.lock
./.venv-v2/Scripts/python.exe -m pip install --no-deps -e .
$RepoMindExe = './.venv-v2/Scripts/repomind.exe'
& $RepoMindExe agent-prepare --output work/v2-sandbox.json
& $RepoMindExe agent-doctor --sandbox-config work/v2-sandbox.json
~~~

无python PATH时可用本机已有C:/Users/czx/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe创建venv。本工作区已准备独立环境，可设置$RepoMindExe为../../work/v2-venv/Scripts/repomind.exe；已有镜像配置在work/v2-sandbox.json。

仅本地V2可用.[dev]轻量安装；platform为可选SDK。锁文件对应本轮Windows/Python3.12，不保证跨平台逐字节一致。wheel不含镜像或样例数据，请在源码包根目录构建，或给agent-prepare指定--project-root。

## 配置和运行

现有.env中的DeepSeek和Langfuse配置继续使用；新机器参考[空模板](.env.example)，不要覆盖已有私密文件。Embedding仍是独立服务；本轮使用事实键，不额外调用Embedding。config不打印key。

~~~powershell
& $RepoMindExe config
& $RepoMindExe agent-bench --data-root data/v2-r2 --dataset data/v2-r2/dev/tasks.jsonl --provider replay --run-id replay-manual-001 --output reports/v2/replay-manual-001.json
& $RepoMindExe agent-bench --data-root data/v2-r2 --dataset data/v2-r2/dev/tasks.jsonl --provider live --run-id live-manual-001 --output reports/v2/live-manual-001.json
~~~

replay三组使用相同人工参考补丁，只验工程。live才调用模型并记录实际请求/token；无价卡时金额未知。原data/v2和首轮真实结果保留；r2只澄清dev-01既有ValueError契约，隐藏断言未改。holdout未调参。

~~~powershell
& $RepoMindExe trace-sync both --outbox reports/v2/live-manual-001.traces.jsonl --dataset-name RepoMind-V2-Dev --receipt reports/v2/live-manual-001-cloud.json
& $RepoMindExe trace-sync both --verify-only --outbox reports/v2/live-manual-001.traces.jsonl --dataset-name RepoMind-V2-Dev --receipt reports/v2/live-manual-001-readback.json
~~~

新测量用新run-id和报告路径；已有状态拒绝覆盖。verify-only不会补发或运行模型。隐藏结果不反馈给当前任务。完整流程还要求正常finish，预算耗尽但代码通过另列，不能全部叫代码错误。

## 测试与边界

~~~powershell
$env:REPOMIND_TEST_AGENT_IMAGE = (Get-Content work/v2-sandbox.json | ConvertFrom-Json).image
./.venv-v2/Scripts/python.exe -m pytest -q -p no:cacheprovider --basetemp work/pytest-v2
~~~

未设置镜像时4项真实Docker测试明确跳过。容器不保证防内核漏洞或蓄意判题作弊；本轮不支持任意外部仓库。规格、样本、生成波动和停止预算限制解释，费用未核账。详见交付说明。

## 保留的旧版本能力

import/query保留事件历史、双时间、冲突和来源；ingest/index/search/source保留引文提取与混合检索；eval/eval-intelligence/compare保留原评测。旧命令不要求Docker，原SQLite schema和冻结数据保留。

历史：[V1设计](docs/architecture.md)、[V1.1](reports/v1.1/acceptance.md)、[V1.2](docs/v1.2-delivery.md)。原requirements/architecture保持V1语境；当前设计见docs/v2-stage-plan.md及ADR0016–0019。
