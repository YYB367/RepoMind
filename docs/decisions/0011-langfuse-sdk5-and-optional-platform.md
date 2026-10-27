# 阶段目标：为 V1.2 采用受支持的 Langfuse SDK 与可选平台依赖

ADR0011；状态：接受；日期：2026-10-27；范围V1.2。新增平台集成已获授权；ADR0004仍保留为V1历史决策，不回写早期版本。

## 原方案与触发原因

V1/V1.1仅保存本地报告，无平台依赖。V1.2要求trace、dataset和experiment，因此需要引入观测SDK，但原有轻量导入/查询不应被迫安装平台栈。

初期考虑Langfuse Python SDKv4+。2026-10-27官方overview已列SDKv5为GA，迁移表指出v5移除deprecated调用并通过OTEL关联实验。部分reference仍保留latest-v4说明；不能只看版本下界或旧示例。[官方SDK](https://langfuse.com/docs/observability/sdk/overview)、[v4→v5迁移](https://langfuse.com/docs/observability/sdk/upgrade-path/python-v4-to-v5)。

## 替代方案比较

| 方案 | 收益 | 取舍 |
|---|---|---|
| 手写旧ingestion/dataset-run REST | 依赖少 | 已公布弃用时间，易误用旧数据模型；不采用 |
| SDKv4+但不查具体调用 | 下界宽 | deprecated方法仍可能可调用，不能保证现代实验路径；不采用 |
| 锁SDK5并核验公开接口与OTEL实验实现 | 与新数据模型一致，官方支持 | 增加SDK/OTEL依赖和兼容测试；采用5.0.4 |
| 基础安装强制引入全部平台SDK | 安装一次覆盖全部 | 初始化、副依赖与home写入影响原用户；不采用 |
| platform extra + 隔离环境 + lazy import | 基础功能保留，平台可复现 | 维护独立锁文件和测试环境；采用 |

## 决策与原理

锁Langfuse5.0.4，平台extra还包含实际核验的Mem0依赖；在隔离v12环境安装并记录完整解析版本。trace使用SDK observation/OTEL，experiment使用已核验runner，dataset及读取用支持的Public API。

Langfuse服务端v4与Python SDKv5是两条版本轴，不意味着服务器须叫v5。SDK5对self-hosted服务器有最低要求；用户选Cloud或self-hosted host后核验兼容，不默认部署服务器或猜地区。[兼容矩阵](https://langfuse.com/docs/compatibility)。

官方公布2026-11-16移除Cloud legacy trace与dataset-run路径；本项目不通过旧trace ingestion或dataset-run-items构造新实现。该结论不泛化成“所有score写入也同日失效”。[弃用映射](https://langfuse.com/faq/all/deprecated-api-migration)。

## 取舍、影响与迁移

新增SDK/OTEL让平台调用更明确，但增加依赖与生命周期管理。原Pydantic/SQLite/argparse入口继续不import平台SDK；缺extra时仅平台命令给出安装诊断。保留V1.1环境、账本、数据和报告，平台输出位于独立run目录。

源码/安装检查只证明接口存在，不能证明云端数据已经收到。真实平台验证按ADR0014执行，flush不能代替ACK。

## 回滚与验证

停用platform命令并恢复V1.1环境即可回退本地工作流；新增报告/outbox仍保留。代码回退不自动删除已创建云端对象。验证包括隔离安装、optional import、实际锁版本公开接口、OTEL/experiment路径与基础回归。未配云端时明示cloud验证待完成。
