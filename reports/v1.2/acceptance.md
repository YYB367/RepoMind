# 阶段目标：验收 V1.2 的受控检索比较与 Langfuse 实验平台

2026-10-28，1.2.0。平台工程验收完成，质量限制保留。

平台测试426 passed；基础环境407 passed、19 skipped。
Langfuse读回核验80条trace、20个dataset item、8个experiment、80份逐题输出及评分。

| 方案 | 离线dev | 离线holdout | 首次live dev 0.55 | live dev 0.2 | 首次live holdout 0.2 |
|---|---:|---:|---:|---:|---:|
| 无记忆 | 2/12 | 1/8 | 2/12 | 2/12 | 1/8 |
| 自研语义 | 12/12 | 8/8 | 2/12 | 7/12 | 8/8 |
| 自研混合 | 12/12 | 8/8 | 7/12 | 8/12 | 8/8 |
| Mem0（受控） | 12/12 | 8/8 | 2/12 | 7/12 | 8/8 |

金标未改写；参数只在dev选择。三次付费运行合计163请求、8036输入token，货币费用未知。

质量仍受主体歧义、未知拒答、小合成样本、live向量不完全一致的限制。结果不代表Mem0默认全流程或真实开发收益。

技术为什么采用、原理、变更和回滚见[完整交付说明](../../docs/v1.2-delivery.md)；复现见[运行说明](../../docs/v1.2-usage.md)。
机器证据：[acceptance JSON](acceptance.json)、[dev云端回执](langfuse-dev-verified.json)、[holdout云端回执](langfuse-holdout-verified.json)、[测试XML](pytest-platform-final.xml)。
