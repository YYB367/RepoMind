# 阶段目标：V2 在受限工具与可核验的容器边界执行样例代码

2026-10-28，接受。V1.2只做事实检索，不执行模型代码。V2需要读取/修改源码、运行pytest和查看diff；工作目录隔离不能阻止代码读取宿主或联网，因此不能用临时目录加subprocess冒充安全隔离。

选择已安装的Docker Desktop Linux引擎，准备只包含Python和固定pytest依赖的镜像。宿主可信调度器只发固定Docker命令，模型无法传shell或Docker参数。运行镜像用不可变image ID并--pull=never；非root、禁网、去capabilities、no-new-privileges、只读root及项目挂载、临时/tmp、CPU/内存/PID/时长/输出限制共同缩小能力。密钥只在宿主模型请求适配器中使用，不通过环境或文件挂载进入容器。

工具只读写新建的专用任务副本，允许写入预定src路径；公开测试和Git元数据不可修改，隐藏判题只在最终评分容器中挂载，不进入模型上下文。路径按组件检查，拒绝父目录、盘符、链接/junction/reparse point和hardlink。Git diff使用固定参数并禁用外部diff/textconv，不执行项目钩子。

复制样例时只采用冻结manifest登记的README、项目配置和源码文件，不将目录中额外出现的.env或其他未登记文件提升为可读输入。即使manifest错误登记了凭证/Git文件，也会按文件类别拒绝。该边界有独立测试；对已有冻结样例的可见文件集合没有改变。

考虑过宿主子进程、AST过滤和新增WASM执行栈。前两者不能可靠隔离普通Python；WASM需要额外解释器与pytest兼容验证，而本机Docker已可用，故本阶段选容器。没有启用--privileged、不挂载Socket、不部署云主机。容器不是虚拟机级别的绝对防护，不声称可安全运行任意恶意项目。

Docker不可用或边界检查失败时停止该项执行，不降级到宿主。超时仅清理带本次随机身份及所有权label的容器，保留工作目录、diff和报告。没有核心SQLite schema迁移；停用新命令即可回滚到V1.2，旧记录与发布包保留。

依据：[Docker容器运行](https://docs.docker.com/engine/containers/run/)。构建、隔离和资源限制必须实际验收，不能只凭命令参数声明通过。
