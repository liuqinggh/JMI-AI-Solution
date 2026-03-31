# Claude Agent SDK 使用规则

## 核心原则
- 优先使用 Claude Agent SDK 原生能力（通过 `query()` 调用），不要自己从零实现 agent loop。
- 所有工具调用必须异步处理，支持 streaming 返回中间思考和结果。
- 推荐模型：claude-sonnet-4-5 或更新版本（工具使用能力最强）。

## SDK 集成位置
- **核心客户端**：`app/agents/client.py` - 封装 SDK 的 `query()` 调用
- **选项构建**：通过 `ClaudeAgentOptions` 配置模型、权限、工作目录等
- **流式处理**：使用 `async for` 处理 SDK 返回的消息流（TaskStartedMessage、AssistantMessage、ResultMessage）

## 工具使用优先级
1. **SDK 内置工具（首选）**：Read/Write/Edit/Glob/Grep/LS 等，用于文件操作、代码编辑等本地任务。
2. **MCP Servers（外部集成）**：仅用于与外部系统交互（数据库、API、第三方服务），通过 `conf/config.yaml` 中的 `mcp_servers` 配置。
3. **自定义工具（谨慎使用）**：必须提供清晰描述、输入示例和输出格式，优先考虑是否可用内置工具实现。

## 安全与权限
- 始终使用 `permission_mode` 和 `allowed_tools` 控制权限（配置在 `app/core/permissions.py`）。
- 危险操作（Bash、文件写入等）必须受限或需要审批。
- 绝不在 skill prompt 或代码中暴露 API Key。
- 配置示例见 `conf/config.yaml` 的 `claude.default_allowed_tools`。

## 执行规范
- 遵循 SDK 的自然流程：Gather Context → Think → Action → Observation。
- 在 FastAPI 中使用 `async for` 方式处理 streaming（见 `app/agents/client.py:85`）。
- 流式事件类型处理：
  - `TaskStartedMessage`：会话初始化，提取 session_id
  - `AssistantMessage`：思考过程，提取 TextBlock 内容
  - `ResultMessage`：最终答案
  - 其他消息：工具调用事件

## 技能系统集成
- 技能定义位置：`.claude/skills/{skill_name}/SKILL.md`
- 加载机制：`app/services/skill_loader.py` 读取 SKILL.md 作为 `system_prompt`
- 通过 `ChatRequest.skill_name` 指定要使用的技能