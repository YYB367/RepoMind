# 阶段目标：V1.2 Evaluation Platform

公平比较受控Mem0与自研MemoryProvider的质量、延迟和实际模型用量，并把固定实验的trace、dataset、experiment显式同步到用户配置的既有Langfuse项目。保留V1/V1.1的项目隔离、双时间、计划/完成/纠错和来源证据；本轮不进入V2代码Agent、OpenViking或Harness优化。

当前为 **1.2.0候选交付**。最终测试、真实比较与cloud验证分别见[V1.2交付记录](docs/v1.2-delivery.md)，不把离线回放或flush当作真实平台验收。上一版V1.1的311项测试和24条真实查询属于历史基线，见[原验收报告](reports/v1.1/acceptance.md)。

## 核心架构与技术选择

| 技术 | 为什么采用 | 在本项目中怎样工作 |
|---|---|---|
| Pydantic＋SQLite事件账本 | 结构化校验、重启持久化、完整审计 | 来源/事件/引文原子写入，显式纠错保留历史；结构合法仍不代表模型理解正确 |
| V1 resolver | 避免相似计划或旧值冒充当前事实 | 命中事实键后取完整历史，按as_of/known_at处理有效时间与当时所知 |
| MemoryProvider | 对照时固定输入与事实规则 | 四variant用同样冻结查询，semantic与Mem0作主比较，hybrid单列 |
| Mem0 OSS＋本地Qdrant | 对照成熟检索实现 | infer=False存同样文档，公开配置走回环Embedding桥；dense受控profile，不是完整原生Mem0能力评测 |
| Langfuse SDK5＋OTEL | 记录可追踪实验，避免旧平台API | 同步既有结果与分数，读回dataset/experiment/observations/scores才确认 |
| 本地outbox | 网络故障时不用重跑模型 | 保存payload与稳定身份，至少一次重传；flush无异常不等于持久化 |
| 实报usage＋可选价卡 | 避免编造token或把未知费用当免费 | 默认cost=null；明确价卡只能生成标记的估算 |

设计和工作顺序见[v1.2-stage-plan.md](docs/v1.2-stage-plan.md)，原理、例子与取舍见[v1.2-technologies.md](docs/v1.2-technologies.md)，完整运行说明见[v1.2-usage.md](docs/v1.2-usage.md)。

## 安装

Python3.11+，Windows PowerShell示例。平台依赖为可选extra；原V1/V1.1用户可继续只安装`.[dev]`。

```powershell
Set-Location 'D:\software\codex\2026-10-26\1-repomind-codex-md-2-repomind\outputs\RepoMind'
python -m venv .venv-v12
.\.venv-v12\Scripts\python.exe -m pip install -e '.[dev,platform]'
$RepoMindExe = '.\.venv-v12\Scripts\repomind.exe'
& $RepoMindExe --version
& $RepoMindExe --help
```

本机PATH没有python时，用下面命令替换创建环境命令：

```powershell
& 'C:\Users\czx\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv-v12
```

本次工作区已准备的平台环境可直接设置`$RepoMindExe = '..\..\work\v12-venv\Scripts\repomind.exe'`。platform锁定Langfuse5.0.4、mem0ai2.2.1、qdrant-client1.20.0；受控环境不额外安装会触发模型下载的spaCy/fastembed组件。

## 配置现有服务

根.env仅在本机编辑，已有文件不要覆盖。程序只读当前目录，系统环境变量优先。`repomind config`显示配置是否存在和SDK版本，不显示URL/key，不请求网络。

V1.2真实比较只需独立Embedding配置；模型和地址沿用用户当前选择：

```text
REPOMIND_EMBEDDING_PROVIDER=openai-compatible
REPOMIND_EMBEDDING_BASE_URL=https://maas.qianwenaiapi.com/compatible-mode/v1
REPOMIND_EMBEDDING_API_KEY=在本机填写Qwen服务Key
REPOMIND_EMBEDDING_MODEL=qwen3.7-text-embedding-flash
REPOMIND_EMBEDDING_DIMENSIONS=1024
REPOMIND_SEARCH_MIN_COSINE=0.55
```

0.55来自V1.1开发集校准，不是通用置信概率。新语料和模型要在dev重新验证；API默认与回放基线的配置单独记录。DeepSeek提取仍有独立配置，不能把聊天key发给Embedding服务。

V1.2的冻结对照采用显式 `compare --min-cosine 0.2`，仅依据新dev选择。CLI兼容默认仍是0.55，环境里的V1.1配置未覆盖；首轮失败、校准过程和首次holdout均见交付记录。云端首次同步若尚未可见，可用相同参数追加 `trace-sync --verify-only` 只读核验，避免重复上传。

既有Langfuse项目需要填写三个独立字段，不预设host或地区：

```text
LANGFUSE_BASE_URL=
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

配置存在不等于cloud已验收；只有显式trace-sync及服务侧读回能证明。未提供Langfuse配置时可完成本地比较并保留outbox，平台状态保持待验证。

## 离线dev对照

```powershell
& $RepoMindExe compare `
  --events data/v1.2/events.jsonl `
  --dataset data/v1.2/dev/questions.jsonl `
  --vector-mode recorded `
  --vectors data/v1.2/recorded-vectors.json `
  --output reports/v1.2/offline-dev-manual-001.md `
  --run-id offline-dev-manual-001 `
  --state-dir work/v12 `
  --outbox work/v12/offline-dev-manual-001/outbox.jsonl `
  --min-cosine 0.2
```

默认运行no_memory、repomind_semantic、repomind_hybrid、mem0。录制向量为人工理想test double，只验证工程管线，不是模型语义准确率。新数据为3项目30事件、12dev/8holdout，金标和输入hash独立冻结；先dev固定参数再首次holdout。

state-dir是父目录，runner新建其下run-id子目录。已存在run、报告、outbox或status会被拒绝，避免旧缓存污染测量。每次新比较用新ID与输出；只重传云端时复用原outbox，不再compare。

真实比较用同样命令改为`--vector-mode live`并去掉`--vectors`，同时换新run-id/output/outbox。该命令向Qwen发送合成问题和文档，实际调用按variant分别计量；同输入向量hash差异会在报告披露。

compare退出0代表运行无执行错误，质量仍需读报告；no_memory低分不会让正常运行变成失败。1表示执行中有错误，2为配置/输入等错误。完整质量、未知拒答、来源与项目串用必须一起看。

## 显式同步到Langfuse

compare不自动上传。填写三个Langfuse字段后，对已经完成的outbox执行：

```powershell
& $RepoMindExe trace-sync both `
  --outbox work/v12/offline-dev-manual-001/outbox.jsonl `
  --dataset-name RepoMind-V1.2 `
  --run-name offline-dev-manual-001 `
  --receipt reports/v1.2/offline-dev-manual-001-langfuse.json
```

同步模式为traces、experiment或both，默认traces。只重放已有output/score，不重新调用模型。receipt与相邻status保存逐对象状态；flush仅表示尝试发送，cloud_verified须有现代API读回核对。仅完整verified退出0，partial为1，输入/配置错误为2。当前上传限明确synthetic记录，不自动上传真实仓库内容。

网络或读取延迟时保留outbox/receipt并显式重试；稳定ID不保证span exactly-once。模型比较、SDK契约测试和cloud持久化证据分别报告。

## 价格与测试

默认费用为null，usage缺失也不算免费。`price-card.example.json`是CNY空models模板，没有真实报价；明确填写模型、单位、日期和出处后可给compare追加`--pricing work/my-price-card.json`。缺价卡、过期、usage或缓存拆分不全时继续报告未知；估算不是账单核验。

```powershell
.\.venv-v12\Scripts\python.exe -m pytest -q --basetemp work/pytest-v12-manual
```

受限临时目录处理、价卡schema、失败恢复及每条命令含义见[v1.2-usage.md](docs/v1.2-usage.md)。实际通过/失败数、live分数和cloud回执由[V1.2交付记录](docs/v1.2-delivery.md)汇总。

## 原V1/V1.1能力与兼容

```powershell
# 结构化事件与确定性历史查询，无模型调用
& $RepoMindExe --db work/demo.sqlite3 import data/fixtures/conversations.jsonl
& $RepoMindExe --db work/demo.sqlite3 query --project CampusRecruit --field database --as-of 2026-03-15
# 自然语言入口默认只生成候选，--apply才原子保存
& $RepoMindExe ingest examples/v1.1-sources.jsonl --output work/candidates-new.jsonl
# 已有账本可先用词法搜索；语义/hybrid查询先index
& $RepoMindExe --db work/demo.sqlite3 search --project CampusRecruit --text 'database' --as-of 2026-04-10 --mode lexical
```

来源可信envelope由调用者指定，模型只提出候选；精确引文证明片段存在，不能保证理解正确。as_of按事实有效时间，known_at按观察截止，日期表示UTC当日末；计划不自动成为事实，未知和冲突保留拒答。schema1→2的备份回滚见[ADR0007](docs/decisions/0007-additive-schema-and-staged-evaluation.md)。

V1.2新增optional依赖、比较和同步，不改写旧账本或冻结金标。停用平台命令可回到V1.1环境；保留报告/outbox与索引，代码回退不自动删除云端对象。旧报告保存在reports/、reports/v1.1；变更历史见[CHANGELOG](CHANGELOG.md)。本项目在本工作区outputs/RepoMind开发，原`D:\projects\RepoMind`规划文件未修改，没有远程推送或平台服务器部署。
