# FastAPI 最佳实践规则

## 项目结构要求
- 使用 APIRouter 按版本组织路由（app/api/v1/）
- 所有 endpoint 必须使用 Pydantic v2 模型定义请求和响应
- 支持 StreamingResponse 用于 agent 中间过程返回

## Endpoint 设计规范
- 路由示例：POST /api/v1/agents/{agent_type}/run
- 使用 Depends() 注入配置、Agent 实例、日志等
- 响应模型严格定义，返回结构包含 status、result、thinking_steps（可选）

## 异步与性能
- 所有 I/O 操作（API 调用、文件、Agent 执行）必须使用 async/await
- 使用 pydantic-settings 从 .env 加载配置（ANTHROPIC_API_KEY、MODEL_NAME 等）

## 错误处理
- 使用全局异常处理器
- 区分客户端错误（422/400）和服务端错误（500）
- 记录详细错误信息，但不暴露敏感数据

当实现新接口时，先检查 app/api/v1/endpoints/ 和 app/schemas/ 中的现有模式。