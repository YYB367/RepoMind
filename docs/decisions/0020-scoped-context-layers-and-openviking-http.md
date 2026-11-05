# 阶段目标

让 RepoMind 在明确的预算内为同一个项目选择证据，并能通过 OpenViking 的原生内容 API 读取目录层级。

## 决策

V2.0 Agent 从事件账本解析明确的事实键，并读取当前运行中此前成功任务的经验。V2.1 加入项目资料选择器，处理面向问题的文档排序和预算约束。事实的双时间解释仍由原 resolver 负责。文档快照中的项目资料需要由调用方维护时效。

上下文选择器先限定项目，再按直接顺序、余弦相似度或目录匹配排列原文。三组复用同一个完整条目打包器。字节预算便于在离线、中文和英文条件下精确复核 JSON 大小。模型协议和各自的 tokenizer 会影响整条请求的 Token，因此报告分别保留字节上限和供应商实报 Token。记录太长时整条跳过会降低召回，短条目仍能进入剩余空间。

OpenViking 的目录使用 L0 摘要和 L1 概览，普通 Markdown 文档经 L2 读取。通过三个 HTTP GET 接口隔离 RepoMind 与 OpenViking 的安装、运行和升级。调用者提供目录清单和固定根路径，服务端权限负责账户隔离，客户端只允许在该根路径内根据合法项目、分组和文档 ID 构造 URI。摘要用来导航，回答依据来自原文。

## 比较过的方案

Python SDK 可以负责导入和检索，依赖较多，也会把库版本和底层存储生命周期带进 RepoMind。当前所需的三个读取契约用标准库 HTTP 即可表达。服务端可以独立安装官方 wheel。

把原文全部加入提示词最容易复现，长文档会很快消耗预算。向量相似度能匹配改写后的词义，但增加建索引和查询调用。分层只深入相关目录，依赖目录组织与摘要质量。原文和规则固定后再测量三者。

另一选择是在客户端绑定特定模型 tokenizer 来分配预算。当前使用可重复核对的字节上限，并从相同回答器收集真实 Token。采用特定 tokenizer 后需要同步维护模型版本与聊天模板。

## 兼容、迁移和回滚

新增 context-select、context-bench 两条命令。项目账本、已保存的经验库和旧数据集无需迁移。启用 OpenViking 时，在独立服务准备相同项目布局，确认目录已有摘要和概览。适配器通过清单决定候选项，不上传或改写服务数据。向量对照在评测开始时构建本轮内存索引，不复用旧缓存。

使用本地选择时省略 OpenViking 根路径。需要回到旧版程序时可使用本地 v2.0.0 标记或既有 wheel。OpenViking 工作目录和测试报告可单独留存。

## 来源

[OpenViking 上下文层级](https://github.com/volcengine/OpenViking/blob/main/docs/en/concepts/03-context-layers.md) · [上游内容路由](https://github.com/volcengine/OpenViking/blob/main/openviking/server/routers/content.py) · [官方安装与部署](https://github.com/volcengine/OpenViking/blob/main/docs/en/guides/03-deployment.md)
