# 阶段目标：为 V1.1 接入用户指定的 Qwen Embedding，并按实际端点选择正确协议

ADR 0009；状态：接受，含2026-10-27真实调用更新；范围：V1.1。保留用户模型、地址与凭据，区分“原生适配已实现”和“当前兼容端点已实测”，不改变DeepSeek提取配置，不新增数据库服务或SDK依赖。

## 原方案与触发原因

最初只有OpenAI兼容embeddings适配。用户随后提供DashScope SDK示例：模型qwen3.7-text-embedding-flash，原生示例base为https://cn-beijing.maas.qianwenaiapi.com/api/v1。因此新增了DashScope原生HTTP适配，能够处理document/query、原生参数与响应，不要求安装SDK。

实际运行时，用户在.env填写的base是 **https://maas.qianwenaiapi.com/compatible-mode/v1**，与此前原生示例不同；模型仍为qwen3.7-text-embedding-flash。端点路径已经表明这是兼容协议入口，不能沿用原生URL拼接规则。

初次仍按native协议追加/services路径，真实请求收到HTTP404。失败保存在[初次协议不匹配记录](../../reports/v1.1/qwen-native-address-mismatch.json)，没有改写成成功。随后保持用户.env中的URL、模型、key不变，仅将公开provider协议选择改为OpenAI-compatible，再按兼容接口调用成功；没有擅自改地区或切换模型。

## 官方协议核验

2026-10-27核验[阿里云同步Embedding接口](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api)：官方分别给出compatible-mode/v1/embeddings与原生/api/v1/services/embeddings/text-embedding/text-embedding两种路径；所选flash模型支持1024/768/512/256维，一批最多20条。原生接口还提供text_type角色参数、text_index响应索引及实际usage。

官方业务空间/区域示例不等于用户账户地址。本次以用户实际配置和真实调用为准，不把文档示例域名自动替换进.env；smoke成功只证明本次账户请求可用，不能据此推断账户归属区域或其他模型权限。

## 替代方案比较

| 方案 | 收益 | 代价与选择 |
|---|---|---|
| 向兼容base追加原生/services路径 | 复用原生适配 | 已真实404；路径协议不匹配，不继续使用 |
| 保留实际base，改用OpenAI-compatible适配 | 匹配用户已填写端点，不改URL/model/key | 当前启用并已smoke成功；没有原生text_type角色参数 |
| 为使用native强制更换base | 可启用原生特性 | 会改变用户实际服务地址或区域选择；不擅自执行 |
| 安装DashScope SDK | 封装URL、序列化和响应 | 当前HTTP接口面小，SDK不会自动消除base协议不匹配；本轮不增加依赖 |
| 保留已实现native适配作为显式可选provider | 支持正确原生base下的角色与原生响应 | 采用；本地协议测试通过，但未在本次用户服务的native URL live验证 |
| 更换数据库或向量服务 | 可扩展索引能力 | 协议差异不需要改SQLite；不采用 |

## 当前启用的兼容协议

当前地址为用户.env实际配置，维度1024：

```text
POST https://maas.qianwenaiapi.com/compatible-mode/v1/embeddings
```

请求使用model、input、dimensions等兼容字段，响应从data[index,embedding]读取。文档和问题通过统一embed请求计算向量，**没有发送原生text_type=document/query参数**。代码层仍能区分索引与查询流程，但不能宣称本次live Qwen使用了原生的非对称角色提示。

本轮smoke为2个Embedding请求，返回1024维，实际usage合计61tokens；相似度仅是少量样本文本的连通性演示，不是保留集成绩或普遍语义效果证明。DeepSeek聊天适配及其独立凭据不受此次Embedding协议切换影响。实际开发/保留集成绩由后续评测报告记录，不由本ADR推断。

## 已实现的原生适配能力

用户的TextEmbedding.call示例表达模型与服务能力选择，SDK本身是HTTP封装。urllib实现的原生可选适配在正确native base下发送：

```text
POST {native base}/services/embeddings/text-embedding/text-embedding
```

```json
{
  "model": "qwen3.7-text-embedding-flash",
  "input": {"texts": ["待嵌入文本"]},
  "parameters": {"text_type": "document", "dimension": 1024, "output_type": "dense"}
}
```

这是原生协议示例，不是当前兼容请求。native index使用document，native查询使用query；问题与事实文档扮演不同检索角色，但仍要处于相同模型空间和维度。原生text_type能力已经有本地HTTP协议测试，尚未在用户本次native服务地址上live验证。

所选模型批次最多20条，适配器分批并验证每条索引、数量、维度、有限非零数值。原生按text_index还原，兼容按index还原。批次上限依据用户所选模型，不推广为所有provider的通用限制。全部向量合法才提交缓存，失败不留半套索引。

## 取舍、凭据与缓存影响

协议边界显式区分native和compatible，仍共用urllib的超时、HTTPS、重定向限制和错误脱敏。Qwen key只用于用户指定的Qwen/Embedding服务，DeepSeek key只用于提取，任何一侧缺配置均不回退到另一侧。报告保存实际请求数和usage，不伪造Token或价格。

缓存指纹必须反映provider适配、base、模型、维度及输入角色策略。native的document/query策略与当前compatible统一embed策略不等价，不能只因模型名和维度相同就混用向量。适配器改变后显式重新index；文本hash继续限定事实键与known_at快照，events、gold和schema2存储不变。

新增native适配本身仍有价值，但本轮实际采用compatible是由用户.env端点和404证据驱动，不是模型能力降级或擅自换服务。没有偷偷修改key、模型、地址或地区，也不因native示例已经实现就忽略真实配置。

## 迁移与回滚

1. 保留schema2事件、旧向量和首次404报告。
2. 当前Embedding配置使用用户实际compatible base和模型，公开provider选择为OpenAI-compatible；DeepSeek配置保持原样。
3. 以当前适配器指纹重新index，验证重启、维度及known_at快照；不能复用native指纹缓存。
4. 在开发数据冻结参数后运行live评测；保留集首次结果单独记录。smoke与test double不能替代质量验收。

若用户以后明确提供可用native base，再显式选择native适配并重新index，单独验证document/query。回滚适配只恢复已明确的provider配置；旧缓存必须指纹和hash完整匹配，否则重建。不需要更换数据库或改写事件；若回退旧V1二进制，仍遵守ADR0007的备份恢复方案。

## 验证状态与限制

native adapter本地协议测试已通过；当前compatible端点真实smoke已成功。初次native-path-on-compatible-base的404完整保留。原生角色参数在本次用户服务上尚未live验证，smoke样本不足以证明检索质量，最终测试与开发/保留指标以验收报告为准。

