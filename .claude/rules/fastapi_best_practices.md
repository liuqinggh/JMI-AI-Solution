# FastAPI 最佳实践规则

## 项目结构要求
- 使用 APIRouter 组织路由，在 `app/api/__init__.py` 中统一注册为 `/api/v1` 前缀
- 路由文件平级放置在 `app/api/` 目录（chat.py, upload.py, health.py）
- 所有 endpoint 必须使用 Pydantic v2 模型定义请求和响应
- 支持 StreamingResponse（SSE 格式）用于 agent 流式返回

## Endpoint 设计规范
- 路由示例：`POST /api/v1/chat`, `POST /api/v1/upload`
- 使用 `Depends()` 注入配置、服务实例等（见 `app/api/chat.py` 中的 `get_settings`）
- 响应模型严格定义在 `app/models/` 目录
- SSE 流式响应格式：
  ```python
  event: session_started
  data: {"sdk_session_id": "..."}
  
  event: assistant_delta
  data: {"text": "..."}
  
  event: final
  data: {"final_answer": "...", "sdk_session_id": "..."}
  ```

## 依赖注入模式
- 配置注入：`settings: Settings = Depends(get_settings)`
- 服务实例化：在路由函数内部创建（如 `SessionManager`, `UploadService`）
- 避免全局状态，优先使用函数级依赖

## 异步与性能
- 所有 I/O 操作（API 调用、文件、Agent 执行）必须使用 async/await
- 配置管理：通过 YAML 文件（`conf/config.yaml`）+ 环境变量覆盖
- 流式响应使用 `async def` 生成器函数

## 错误处理
- 使用 HTTPException 返回标准错误（见 `app/services/skill_loader.py:15`）
- 区分客户端错误（422/400/404/409）和服务端错误（500）
- 记录详细错误信息，但不暴露敏感数据（如 API Key、内部路径）
- 流式响应中的错误通过 `event: error` 返回

## 实现新接口时的检查清单
1. 查看 `app/api/` 中现有路由的实现模式
2. 在 `app/models/` 中定义请求/响应模型
3. 如有业务逻辑，抽取到 `app/services/` 层
4. 在 `app/api/__init__.py` 中注册新路由
5. 添加对应的测试到 `tests/` 目录