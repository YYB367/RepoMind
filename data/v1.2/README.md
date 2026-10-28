# 阶段目标：用独立冻结数据比较 V1.2 受控记忆检索后端

本数据集只输入结构化事实与查询，不做自然语言事实提取。事件和查询的expected_key/status/value/source_ids均由人工独立设计，没有使用产品resolver/provider/search或真实模型输出生成金标。

## 组成与划分

| 文件 | 用途 |
|---|---|
| events.jsonl | 3个新项目各10条事件，共30条 |
| dev/questions.jsonl | 前两个项目的12条开发查询 |
| holdout/questions.jsonl | 第三个项目及无记录scope的8条保留查询 |
| recorded-vectors.json | 人工one-hot向量精确输入查找表，仅用于协议/管线测试 |
| manifest.json | 行数、分类、分割、约束、字节数与SHA-256 |

文件使用UTF-8无BOM、LF换行，JSONL最后保留一个LF。模型输入hash对字节敏感，不要用平台默认写入方式重新格式化已冻结文件。

## 对照范围

Mem0使用infer=False存同样fact-key文档，其他有记忆variant使用相同文档、项目/known_at范围、top_k、余弦门槛和共享V1 resolver。主要比较repomind_semantic与受控Mem0，hybrid独立列为策略增强，不能称为完整原生Mem0能力排名。

先加载全部事件，再按项目和known_at过滤构建文档；as_of由事实有效时间决定。默认当前知识可使用晚到观察重建过去；有known_at时只能使用该观察截止前的记录。未记录属性、无记录scope和已知键暂无有效事实分别体现在expected_key=null或已知键+unknown中。

覆盖declare、plan、complete、correct、同生效时间冲突、晚到完成、历史known_at、未知拒答和项目/主体范围。题量小、字段词汇与规则家族共享，不能声称模板完全独立或代表真实仓库问题覆盖率。

## 人工向量不是语义成绩

录制资产声明kind=recorded_test_double，fingerprint=recorded:v1.2-controlled-one-hot，real_model_quality=false。每个完整(subject,predicate)事实键一个one-hot维度，额外未知维度与全部文档正交；查询在资产制作时按人工expected_key指定维度，运行时只拿到精确text hash查找表，不接收金标字段。未录制文本必须报错，不猜测向量。

Event/时间规范化及build_documents只用于验证输入和计算文档hash，不生成或调整标准答案。向量资产覆盖每个项目完整历史及query需要的known_at快照；query输入共同将换行规范化为空格。此数据只能验证受控管线与排名行为，不能证明真实模型语义理解、泛化或费用优化。

## 冻结与验收

manifest记录最终hash。先dev开发/校准并固定配置，再首次holdout；保留首次结果与修复结果，不根据产品输出改金标。录制与live报告分开；真实模型的向量hash差异、实际usage和冷/热条件另行记录，不能把回放零调用称为某个后端免费。

主体干扰保留：project.database与worker.database是不同事实键，理想向量分别给独立维度。这只让合同测试保留已知主体语义；真实Qwen能否区分须实测并如实报告，不因结果改金标。
