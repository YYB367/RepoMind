# 阶段目标：V2.0 让记忆参与可自动验收的真实代码修改任务

授权依据：用户在V1.2交付后要求“进行下一阶段”；主执行提示词的V2.0路线和规划归档作为范围依据。2026-10-28开始，分支feature/v2-developer-agent。旧版本初始“只做V1”的闸门已有后续逐阶段授权，当前不越过V2.0。

## 交付与范围

实现有限步Developer Agent循环，提供list_files/read_file/write_file/run_tests/git_diff/finish。工具只作用于专用样例仓库副本；不接受任意宿主shell命令，不修改真实用户项目，不自动安装或执行模型要求的依赖。

固定10个开发任务，6个dev、4个holdout，覆盖金额精度、运费边界、标识符、重试、时间、库存、折扣、游标、历史规范和冲突合并。它们是带真实Python源文件和pytest用例的合成开发基准，不冒充生产仓库或公开SWE基准。任务、历史事件、公开测试和隐藏验收测试由人工定义，冻结hash后不按模型输出改金标。

三组共用模型、任务、初始代码、工具、上下文上限、测试与步数预算：baseline不注入历史；memory使用当前事实记忆；enhanced按任务as_of/known_at解析事实，并可读本轮此前成功任务形成的经验。该定义是显式消融，不代表所有Memory Agent。经验只存已验收任务的公开交互总结，不复制隐藏测试或判题信息。每组独立账本/工作目录；开发集和保留集经验隔离，保留集不反哺调参。

## 隔离先于代码执行

本机Docker Desktop已安装，Linux引擎实测就绪。用明确构建的Python/pytest镜像；运行只接受本地不可变image ID，禁止自动拉取。每次测试建立独立容器，network=none、非root、cap-drop ALL、no-new-privileges、只读root和只读项目/判题挂载，仅/tmp可写；限制CPU、内存、进程数、时间与输出。镜像构建可安装固定的公开依赖，模型执行阶段不联网。

Docker不可用时fail closed，不降级成宿主subprocess pytest或把临时目录称作沙箱。容器共享内核，不能承诺防御内核漏洞；本阶段只使用本地已知样例，不运行任意第三方项目。文件工具拒绝绝对路径、父目录、链接/reparse point、hardlink和受保护文件；模型不接触.env、.git、隐藏判题文件或Docker Socket。

## 实施顺序与验收

先设计并验证容器、路径和资源边界，再开发动作协议/模型适配/工具循环/经验存储，最后冻结任务、运行离线协议与真实模型对照。dev可修实现和固定参数，首次holdout结果保留，不调整金标，不以低分掩盖工程失败。

结果包括任务成功率、公开测试失败/修复次数、工具拒绝、实际模型请求/token、准备/模型/工具/判题耗时、逐任务diff及失败原因。费用无有效价卡时为null，不猜价格。Langfuse只回放已经完成的合成任务记录，不重跑模型，读取任务输出和评分后才标cloud_verified。

工程门槛为旧回归保持通过、隔离测试通过、三组对照完整可运行、来源/项目范围不泄漏；质量分数如实报告，不预设增强组必胜。实际代码任务对记忆的依赖、样本小、模型波动和判题抗作弊能力有限都必须说明。不做V2.1/V3或GUI。

## 选择依据

沿用Python/Pydantic/SQLite/argparse和已有DeepSeek HTTP适配，新增Docker执行边界；不为有限状态循环引入Agent框架。DeepSeek JSON动作经过schema验证才分派，JSON合法不等于动作可执行。记忆使用显式事实键以减少V1.2语义检索弱点对本轮执行评测的混杂。

参考：[Docker运行与权限](https://docs.docker.com/engine/containers/run/)、[DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/)。版本、镜像digest、实际接口和限制以本轮运行记录为准。
