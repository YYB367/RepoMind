# 阶段目标：以受控 MemoryProvider 对照 Mem0 与自研检索，并保持事实规则一致

ADR0012；状态：接受；日期：2026-10-27；范围V1.2。比较检索实现，不宣称复现Mem0原生抽取、纠错或整个端到端产品。

## 原方案与触发原因

V1.1只有自研semantic/hybrid检索，无法区分成熟记忆组件是否能改善相同输入下的候选质量。V1.2增加统一MemoryProvider边界与Mem0 OSS对照，四variant为no_memory、repomind_semantic、repomind_hybrid、mem0。

实际核验mem0ai2.2.1构造与工厂后，直接传任意embedder实例或调用公开register_provider的假设不成立。SDK还可能在可选spaCy/fastembed存在时加载模型，默认状态/遥测与home路径也可能污染受控实验。

## 替代方案比较

| 方案 | 收益 | 取舍 |
|---|---|---|
| 直接比较默认Mem0全流程与自研完整链 | 覆盖产品使用体验 | 模型抽取、排序和状态规则同时不同，难以归因；本轮不做 |
| infer=False存同样fact-key文档，共享resolver | 固定事实与时间语义，检索错误可分离 | 采用，结论限定为当前受控profile |
| patch私有工厂注入embedder | 代码看似短 | 公共契约不成立、升级脆弱；不采用 |
| 引LangChain桥接 | 有现成集成 | 多一个框架且其embed路径角色行为不符合本实验边界；不采用 |
| 公开OpenAI配置→回环Embedding桥→既有provider | Mem0真实add/search执行，复用Qwen/recorded配置与usage | 采用；需管理本地HTTP、锁和错误路由 |
| 运行Mem0所有可选检索模型 | 更多原生功能 | 可能隐式下载，实验变量增加；另立未来profile，不混入当前结果 |

## 决策与公平契约

每个有记忆variant使用同样project/known_at快照和fact-key文档、相同模型/维度/top_k/min_cosine，命中键后共用V1 resolver。输入共同规范化换行为空格，避免Mem0 embedder内部处理导致两侧文本不同；记录规范文本hash。

主比较为repomind_semantic与mem0。hybrid增加词法/RRF，单列为策略增强；no_memory返回无证据，作为记忆依赖基线。不能将四者包装为通用Agent排行榜。

Mem0 infer=False跳过LLM抽取。当前controlled profile在独立环境不安装spaCy/fastembed可选模型依赖，避免隐式下载；检测到不符合profile的可选组件应明确失败并提示使用锁环境。报告注明dense-only/optional features absent，不把结果称为完整Mem0多信号能力。

Mem0公开search过滤绑定项目/快照对应的user/run，保留SDK排名、backend score与解释字段。共同门槛按semantic_score核验，统一严格边界；最终融合score不能冒充余弦。若未来启用BM25/entity，应新建profile与报告，重新讨论比较结论。

## 公共配置桥与隔离原理

Mem0公开OpenAI embedder连接本进程回环桥，桥仅提供Embedding协议并转发到本项目已有provider；用户真实模型key不进入Mem0本地请求，回环凭据与远程key不同。外层串行/锁明确document与query操作，非Embedding或意外LLM路由拒绝，不隐式访问外网。

首次import前设置MEM0_DIR至run目录并禁MEM0_TELEMETRY，Qdrant path/history路径均显式配置。创建/关闭Memory及自有Qdrant client，避免SDK只关闭history仍遗留索引锁。SQLite账本保持权威；Mem0索引可以由同样文档重建。

## 向量模式与测量边界

offline使用完全相同recorded向量字节，real_model_quality=false；live各variant独立client，以同文本/model/参数请求，分别记实际usage。若query/doc向量hash不同，报告flag，不把模型浮点或网络波动误归因后端。不新增shared_live第三模式。

## 兼容、回滚与验证

MemoryProvider仅覆盖本轮index/search与结果映射，不扩成通用Agent插件框架。停用Mem0可回到自研入口，保留run目录与报告，不改旧事件或金标；不要静默删除本地或云端历史。

验证包括真实锁SDK的add/search、infer=False无LLM调用、项目/快照过滤、score门槛、重复/重启、目录/遥测、可选模型下载拦截、桥路由与关闭行为。版本升级需复验公共边界。当前设计不能代替真实SDK与live测量结果。

依据：2026-10-27查阅[Mem0 ADD](https://docs.mem0.ai/core-concepts/memory-operations/add)、[OSS配置](https://docs.mem0.ai/open-source/configuration)及本轮mem0ai2.2.1 wheel公共源码核验。动态main参考为[官方memory实现](https://github.com/mem0ai/mem0/blob/main/mem0/memory/main.py)，最终行为以锁版本实测为准，不直接引用其公布benchmark排名。
