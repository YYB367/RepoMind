# ADR 0004：本轮仅本地 CLI，不部署复杂平台

- 状态：接受；日期：2026-10-26；范围：P0 与 V1。
- 背景：Mem0、OpenViking、Langfuse 和 Agent 平台是研究参考；部署全部组件妨碍核心规则验收。
- 决策：使用 Python 3.11+、Pydantic、SQLite、JSONL、pytest 和标准库 argparse。argparse 满足三个命令及帮助/错误处理，不引入额外 CLI 框架依赖。不做 GUI、云部署或真实代码工具 Agent。
- 替代方案：Typer 更丰富但增加依赖；Web 前端、Docker 与外部评测服务没有 V1 必须解决的问题。
- 后果：运行路径简单，缺少交互界面和在线 trace。评测报告以 Markdown/JSON 保存，平台接入到 V1.2 再决定。
- 验证：README PowerShell 命令可复制运行；评测产生双格式报告；依赖与功能审计符合版本边界。验收通过后不自动进入后续版本。
