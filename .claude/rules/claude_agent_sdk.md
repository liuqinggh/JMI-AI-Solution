# Claude Agent SDK 使用规则

## 核心原则
- 优先使用 Claude Agent SDK 原生能力（query() 或 ClaudeSDKClient），不要自己从零实现 agent loop。
- 所有工具调用必须异步处理，支持 streaming 返回中间思考和结果。
- 推荐模型：claude-3-5-sonnet-20241022 或更新版本（工具使用能力最强）。

## 工具使用优先级
1. SDK 内置工具（首选）：Read/Write/Edit/Bash 等，用于文件操作、代码编辑等本地任务。
2. MCP Servers（外部集成）：仅用于与外部系统交互（数据库、API、第三方服务），避免过度复杂化。
3. 自定义工具（谨慎使用）：必须提供清晰描述、输入示例和输出格式，优先考虑是否可用内置工具实现。

## 安全与权限
- 始终使用 permission_mode 和 can_use_tool hook 控制权限。
- 危险操作（Bash、文件写入等）必须 sandbox 或人工审批。
- 绝不在 prompt 中暴露 ANTHROPIC_API_KEY。

## 执行规范
- 遵循 Gather Context → Think → Action → Observation 循环。
- 在 FastAPI 中使用 async for 方式处理 streaming。
- 每次 tool call 后记录日志（输入/输出/思考过程）。

需要 MCP 示例或具体工具实现时，参考 app/agents/tools/ 目录。