# 阶段目标：V1.1 Intelligent Memory

让自然语言会话变成有原文引文的候选事实；用词法、Embedding或混合检索找到相关属性，再由V1时间规则给出答案。保留计划/完成/纠错、项目隔离和完整历史。本阶段不进入V1.2平台集成、V2代码Agent或V3自优化。

当前发布版本为 **1.1.0**。已验证 **311项测试全部通过**；DeepSeek＋Qwen真实开发集16/16查询，首次保留集8/8查询；旧V1评测32/32＋16/16保持通过。真实模型测量、离线回放和初次失败分别保留，详见 [V1.1交付与验收](reports/v1.1/acceptance.md)。

## 为什么用这些技术，原理是什么

| 技术 | 在这里解决的问题 | 工作原理与边界 |
|---|---|---|
| Pydantic | 模型输出可能缺字段、填错类型或伪造范围 | 按显式契约校验；project/source/观察时间来自可信封装，模型只能给候选。结构合法不代表事实正确 |
| DeepSeek JSON Output | 从会话提取declare/plan/complete/correct | HTTP发送来源文本与当前项目上下文，返回JSON候选；本地再次验证字段、时间、纠错目标和精确原文引文 |
| SQLite事件账本 | 重启后保留来源、旧事实和纠错 | 事务将来源/事件/引文一起提交，任意失败全部回滚；不直接覆盖历史 |
| Embedding＋余弦 | 允许不同问法找到同一属性 | 把属性文档与查询映射为向量，比方向接近程度；模型与维度必须一致，真实效果取决于所选模型 |
| 词法＋RRF | 同时利用明确关键词和语义候选 | 两路各自排序，以1/(60+名次)融合；相似度只负责找属性，不决定实际事实 |
| SHA-256缓存 | 避免旧文本、不同模型或未来知识污染索引 | 缓存绑定项目、属性、模型指纹、观察快照和文档hash；变更后显式重新index |
| argparse＋pytest | 命令可复现，错误可以定位 | CLI输出JSON和明确退出码；分层测试协议、持久化、提取、检索和最终答案 |

更详细的例子、公式和替代方案见 [技术原理说明](docs/v1.1-technologies.md)。本轮没有增加SDK、NumPy、向量数据库或外部平台依赖：两个非流式HTTP接口和小数据量可先用标准库完成；若以后需要更多协议能力，应另写ADR再变更。

## 技术变更与兼容性

- **V1不调用模型 → V1.1显式调用模型**：给结构化内核增加自然语言入口；原import/query/eval继续可用。模型只提出候选，不获得覆盖账本的权限。[ADR0005](docs/decisions/0005-constrained-extraction.md)
- **精确属性查询 → 先找属性再解析历史**：直接挑相似事件会让旧值或计划抢占答案；本轮按完整事实键检索，再运行原resolver。[ADR0006](docs/decisions/0006-hybrid-key-retrieval.md)
- **SQLite schema 1 → 2**：新增来源、提取引文与向量缓存表，原events内容保留。升级在单个事务内；旧V1程序不能读取schema2，回滚需恢复升级前数据库备份，不能只改版本号。[ADR0007](docs/decisions/0007-additive-schema-and-staged-evaluation.md)
- **统一strict schema假设 → 按DeepSeek实际能力适配**：DeepSeek的Chat接口用json_object/max_tokens；本地Pydantic和原文校验继续执行。Embedding采用独立地址、Key和模型，禁止把聊天Key偷偷转发给另一服务。[ADR0008](docs/decisions/0008-deepseek-compatible-output.md)

后续交付固定先写目标，再写技术原因、原理、变更取舍和迁移/回滚，规则已保存到 [AGENTS.md](AGENTS.md) 与 [交付规范](docs/delivery-standard.md)。

## 安装与本机立即运行

Python 3.11+，当前已验证Windows PowerShell与Python3.12。业务依赖仍只有Pydantic；pytest是测试依赖。无需激活脚本或改变ExecutionPolicy。

```powershell
Set-Location 'D:\software\codex\2026-10-26\1-repomind-codex-md-2-repomind\outputs\RepoMind'
# 本机PATH没有python时，使用以下解释器创建环境：
& 'C:\Users\czx\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -e '.[dev]'
$RepoMindExe = '.\.venv\Scripts\repomind.exe'
& $RepoMindExe --version
```

普通环境可用 `python -m venv .venv` 替换创建环境的首条命令。本次工作区已有安装环境，可以直接设置：

```powershell
$RepoMindExe = '..\..\work\acceptance-venv\Scripts\repomind.exe'
& $RepoMindExe --help
```

## 配置DeepSeek Key

根目录的 `.env` 已创建；仅需在 `DEEPSEEK_API_KEY=` 后填写真实Key并保存。程序从当前目录自动读取，不向上搜索其它目录。系统环境变量优先于文件；不执行变量替换、脚本或命令。

新副本可执行 `Copy-Item .env.example .env` 创建配置；**已有.env时请直接编辑，避免覆盖密钥**。

```text
DEEPSEEK_API_KEY=在本机填写真实Key
REPOMIND_PROVIDER=deepseek
REPOMIND_BASE_URL=https://api.deepseek.com
REPOMIND_CHAT_MODEL=deepseek-flash
REPOMIND_CHAT_FORMAT=json_object
REPOMIND_TIMEOUT_SECONDS=60
```

```powershell
& $RepoMindExe config
```

config只显示是否配置及模型名，不显示Key、不请求网络。`.env`被Git忽略且不进入交付压缩包，`.env.example`只有空占位。DeepSeek使用JSON Output和本地校验；当前模型名依据2026-10-27官方文档，可按账户实际可用模型修改。

Embedding需要独立的 `REPOMIND_EMBEDDING_BASE_URL`、`REPOMIND_EMBEDDING_API_KEY`、`REPOMIND_EMBEDDING_MODEL`。当前DeepSeek官方API参考未列出该端点，因此只有聊天Key时先使用`--mode lexical`；不隐式改用其它服务。

本次已验证的向量配置如下。地址按你实际填写的兼容格式使用；模型名保持你指定的版本。原生DashScope的`/api/v1`路径对应另一种协议，不能把两种路径直接拼接混用。

```text
REPOMIND_EMBEDDING_PROVIDER=openai-compatible
REPOMIND_EMBEDDING_BASE_URL=https://maas.qianwenaiapi.com/compatible-mode/v1
REPOMIND_EMBEDDING_API_KEY=在本机填写Qwen服务Key
REPOMIND_EMBEDDING_MODEL=qwen3.7-text-embedding-flash
REPOMIND_EMBEDDING_DIMENSIONS=1024
REPOMIND_SEARCH_MIN_COSINE=0.55
```

0.55是在开发集上校准的保守门槛，不是通用正确概率；更高门槛可能漏掉弱语义匹配。可用`--min-cosine`显式覆盖。原生适配的document/query角色与20条拆批已有本地协议测试；当前真实配置采用兼容接口的默认输入语义。

## 自然语言提取与可审阅写入

```powershell
# 默认仅生成候选与.audit.json，不写入记忆账本
& $RepoMindExe ingest examples/v1.1-sources.jsonl --output work/candidates.jsonl
# 明确apply时，来源、事件和引文才一起提交
& $RepoMindExe --db work/demo.sqlite3 ingest examples/v1.1-sources.jsonl --output work/candidates.jsonl --apply
& $RepoMindExe --db work/demo.sqlite3 search --project CampusDemo --text 'database' --as-of 2026-03-15 --mode lexical
& $RepoMindExe --db work/demo.sqlite3 search --project CampusDemo --text 'database' --as-of 2026-04-10 --mode lexical
& $RepoMindExe --db work/demo.sqlite3 source --project CampusDemo --source-id demo-april
```

示例数据为合成消息。live ingest会向所配置模型发送这些消息和同项目上下文并产生模型用量；没有隐藏重试。默认非思考模式、输出token上限2048。候选工件是提取审计，不是事务提交回执；是否提交以CLI的applied/import结果和账本为准。

模型拒绝、截断、坏JSON、无效字段、找不到原文引文或错误纠错目标都会报错，不写入半批数据。精确引文只能证明文字存在，仍需查看候选是否正确理解原文。日期必须有明确时区；计划日期不会自动变成完成日期。

相同project_id/source_id且内容不变时，重复ingest会复用已保存的提取事件和引文，避免随机输出不同长度引文而产生新事件；不再次调用模型。想重新提取或修订来源时使用新的source_id，不能悄悄覆盖同一来源。

## 语义与混合检索

配置独立Embedding服务后，先显式建立索引，再查询：

```powershell
& $RepoMindExe --db work/demo.sqlite3 index --project CampusDemo
& $RepoMindExe --db work/demo.sqlite3 search --project CampusDemo --text 'Which database is in use?' --as-of 2026-04-10 --mode hybrid
```

index只向模型发送所选项目的属性历史。search读取匹配的缓存，嵌入查询一次；缺缓存、模型改变、文档变化会明确要求重新index，不在查询中偷偷批量生成向量。相同模型指纹必须保持同一维度。

`as_of`按事实生效时间查询；`known_at`按观察时间过滤已知记录。日期表示UTC当日末。审计快照必须在index和search使用相同known_at；不同快照缓存可以并存。命中属性后仍按完整历史处理计划、完成、纠错和冲突。检索未命中返回空hits；已找到但没有有效事实时，结果为unknown；同时间未解决矛盾为insufficient_evidence。

## 评测和测试

V1.1分别报告提取precision/recall、检索Recall@3/Top1、最终答案与来源。固定新数据为18条自然语言case、24条查询；开发12case，保留6case。标准答案独立编写，数据hash冻结。录制提取响应与人工理想向量仅验证工程管线，不是真实模型准确率或语义质量。

```powershell
# 完全离线的链路回放
& $RepoMindExe eval-intelligence --dataset data/v1.1/dev/cases.jsonl --vectors data/v1.1/recorded-vectors.json --search-mode hybrid --output reports/v1.1/offline-dev.md
# 已配置两个真实服务：DeepSeek提取＋Qwen混合检索
& $RepoMindExe eval-intelligence --provider live --dataset data/v1.1/dev/cases.jsonl --search-mode hybrid --min-cosine 0.55 --output reports/v1.1/live-dev-new-run.md
```

每次生成同名JSON与Markdown；保留集仅在开发集和核心测试稳定后首次运行。阈值与实测结论见验收报告；实际模型结果不修改冻结答案来迎合程序。没有Embedding模型的真实报告保持部分验收状态。

真实首次dev曾为13/16最终查询；修复候选诊断/完整JSON示例并仅用dev校准检索门槛后为16/16，之后首次holdout为8/8。原失败报告保留。样本小且许多问题包含明确属性名，不能据此宣称混合检索优于词法或已经达到生产稳定性。

受限会话的系统临时目录不可访问时，可这样运行测试：

```powershell
New-Item -ItemType Directory -Force '../../work/tmp' | Out-Null
$env:TEMP = (Resolve-Path '../../work/tmp').Path
$env:TMP = $env:TEMP
& '..\..\work\acceptance-venv\Scripts\python.exe' -m pytest -q --basetemp '../../work/pytest-v11-manual'
```

CLI退出码：0为命令成功或严格评测全过；1为评测有失败项（报告仍保留）；2为输入/配置/数据库错误。有效的unknown/insufficient_evidence查询仍退出0。eval的数值门槛与整阶段真实模型验收状态单独列出，不能把退出0理解为生产可靠性保证。

## V1兼容与文件位置

原import/query/eval入口继续可用；原60事件、48题与V1报告不覆盖。V1验收为88项测试通过、开发32/32、保留首次16/16，详见 [原验收记录](reports/acceptance.md)。新回归结果另存reports/v1.1。

核心代码在 `src/repomind/`，智能入口在 `intelligence/`；协议与数据在 `domain/`，事件/解析器在 `memory/`，存储在 `adapters/sqlite.py`，评测在 `evaluation/`。设计与原理在docs，新固定输入在data/v1.1，实际运行结果在reports/v1.1。

本次始终在本工作区 `outputs/RepoMind` 开发；`D:\projects\RepoMind` 中原规划未修改。项目保留本地Git历史和旧v1.0.0标签，不推送远程、不部署。
