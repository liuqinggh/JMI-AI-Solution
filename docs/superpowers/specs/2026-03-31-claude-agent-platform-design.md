# Claude Agent Platform MVP 规格说明

## 1. 目标

在当前仓库中重建一个基于 FastAPI + Claude Agent SDK 的平台型服务，作为通用 Skill 部署底座。

本次只交付 MVP，重点覆盖以下能力：

- 基于 `conf/` YAML 的统一配置加载
- 保留 `/api/v1` 前缀的健康检查、上传、对话接口
- `business_session_id -> sdk_session_id` 的平台侧映射
- 基于 `.claude/skills/<skill_name>/SKILL.md` 的 Skill 装载
- 基于配置定义的 App 解析
- 仅允许 Claude Agent SDK 原生工具，默认关闭 MCP
- 上传与对话严格分离

## 2. 范围边界

### 本次实现

- `GET /api/v1/health`
- `POST /api/v1/upload`
- `POST /api/v1/chat`
- 本地文件型 session mapping 存储
- 本地临时上传目录
- Claude Agent SDK 调用封装与 `resume`
- 按 `app_id` 或 `skill_name` 选择 Skill / 工作目录 / 权限
- 可测试的最小 streaming 响应协议

### 明确不做

- Redis 真实接入
- Vertex AI 真实环境联调
- MCP Server 动态注册与外部系统集成
- 平台管理后台
- 旧版 JMI 专用接口兼容
- 历史 `app.api.v1.agent/messages` 兼容层

## 3. 总体架构

### 3.1 模块划分

```text
app/
├── main.py
├── api/
│   ├── health.py
│   ├── upload.py
│   └── chat.py
├── agents/
│   └── client.py
├── core/
│   ├── config.py
│   ├── session_manager.py
│   └── permissions.py
├── models/
│   ├── app.py
│   ├── chat.py
│   ├── session.py
│   └── upload.py
└── services/
    ├── app_registry.py
    ├── skill_loader.py
    ├── upload_service.py
    └── workspace_service.py
```

### 3.2 职责边界

- `core/config.py`
  负责读取 `conf/config.yaml`，根据 `ENV` 合并 `conf/config.<env>.yaml`，并用 Pydantic V2 做校验。
- `core/session_manager.py`
  负责保存和读取 `business_session_id -> sdk_session_id` 的映射，MVP 使用本地 JSON 文件实现。
- `core/permissions.py`
  负责根据平台配置和 app 配置生成 Claude Agent SDK 可用工具与权限模式。
- `services/app_registry.py`
  负责从配置中解析 app 定义，得到 skill、cwd、权限配置。
- `services/skill_loader.py`
  负责加载 `.claude/skills/<skill_name>/SKILL.md`，为 Agent 组装系统提示上下文。
- `services/upload_service.py`
  负责上传文件校验、落盘、元数据保存和 `file_id` 查询。
- `services/workspace_service.py`
  负责将上传文件按本轮会话拷贝到目标工作目录，保证 SDK 原生 `Read` 工具可访问。
- `agents/client.py`
  负责 Claude Agent SDK 的统一调用、事件转换、`resume` 接续和最终结果汇总。
- `api/*.py`
  只处理 HTTP 协议、参数校验、依赖注入和响应序列化。

## 4. 配置设计

### 4.1 配置文件

- 默认加载 `conf/config.yaml`
- 如果环境变量 `ENV=dev`，再叠加 `conf/config.dev.yaml`
- 如果环境变量 `ENV=prod`，再叠加 `conf/config.prod.yaml`

### 4.2 配置模型

```yaml
app:
  name: Claude Agent Platform
  version: 0.1.0
  environment: dev
  host: 0.0.0.0
  port: 8000

claude:
  model: claude-sonnet-4-5
  permission_mode: default
  default_allowed_tools:
    - Read
    - Write
    - Edit
    - MultiEdit
    - Glob
    - Grep
    - LS
  mcp_enabled: false
  mcp_servers: []
  env: {}

session:
  storage_dir: runtime/sessions
  mapping_ttl_seconds: 604800

upload:
  temp_dir: uploads/temp
  max_file_size_mb: 20
  allowed_extensions:
    - .txt
    - .md
    - .json
    - .csv
    - .pdf

security:
  can_use_tool_hook: true
  require_approval_for_write: true

logging:
  level: INFO

apps:
  default:
    skill_name: fastapi-dev
    cwd: .
    permission_mode: default
    allowed_tools: []
```

### 4.3 配置原则

- 平台行为由 `conf/` 决定，不从代码中硬编码业务配置。
- App 级别配置可覆盖平台默认的 `permission_mode` 和 `allowed_tools`。
- 默认禁用 MCP；即使配置中存在 `mcp_servers`，也只有在 app 显式启用时才可传递给 SDK。

## 5. App 与 Skill 机制

### 5.1 App

`App` 是平台上的一个可运行实例，至少包含：

- `app_id`
- `skill_name`
- `cwd`
- `permission_mode`
- `allowed_tools`

MVP 阶段，App 仅从配置中读取，不引入数据库或管理接口。

### 5.2 Skill

- Skill 标准路径固定为 `.claude/skills/<skill_name>/SKILL.md`
- 若 `skill_name` 不存在，接口返回 `404`
- `/chat` 可以只传 `skill_name`，此时平台生成一个临时 App 上下文：
  - `cwd` 默认使用项目根目录
  - 权限默认继承平台配置

## 6. 会话管理

### 6.1 模型

- `business_session_id`
  用户和业务层可见的会话标识
- `sdk_session_id`
  Claude Agent SDK 首轮执行后返回的内部会话标识

### 6.2 存储

MVP 使用本地 JSON 文件：

- 目录：`runtime/sessions/`
- 文件：`runtime/sessions/<business_session_id>.json`

示例结构：

```json
{
  "business_session_id": "biz_123",
  "sdk_session_id": "sdk_abc",
  "app_id": "default",
  "skill_name": "fastapi-dev",
  "created_at": "2026-03-31T12:00:00Z",
  "updated_at": "2026-03-31T12:05:00Z"
}
```

### 6.3 行为

- 首次 `/chat`：
  - 不传 `resume`
  - SDK 返回 `session_id`
  - 平台捕获后建立映射
- 后续 `/chat`：
  - 根据 `business_session_id` 查找 `sdk_session_id`
  - 自动以 `resume=sdk_session_id` 继续对话

## 7. 文件上传设计

### 7.1 `POST /api/v1/upload`

职责仅包括：

- 接收 multipart 文件
- 校验扩展名和大小
- 安全化文件名
- 保存到临时目录
- 生成 `file_id`
- 返回文件元数据

返回示例：

```json
{
  "files": [
    {
      "file_id": "file_xxx",
      "original_name": "a.pdf",
      "saved_path": "uploads/temp/file_xxx_a.pdf",
      "size": 1024,
      "content_type": "application/pdf"
    }
  ]
}
```

### 7.2 约束

- `/upload` 不直接触发 Agent
- 上传成功后文件只是临时资产，只有在 `/chat` 引用 `file_ids` 时才进入工作目录
- 文件元数据与文件本体都保存在本地，方便测试

## 8. 对话接口设计

### 8.1 `POST /api/v1/chat`

请求字段：

- `message: str`
- `business_session_id: str`
- `app_id: str | null`
- `skill_name: str | null`
- `file_ids: list[str]`

约束：

- `app_id` 与 `skill_name` 至少提供一个
- 同时提供时，优先使用 `app_id`，并校验其 `skill_name` 一致性

### 8.2 内部流程

1. 解析 app 上下文
2. 加载 Skill 文本
3. 查询已有 session mapping
4. 将 `file_ids` 对应文件拷入工作目录下的本轮上传区域
5. 组装用户 prompt，明确哪些文件已可通过原生文件工具读取
6. 调用 Claude Agent SDK
7. 首轮时捕获 `sdk_session_id`
8. 持久化 session mapping
9. 将 SDK 事件转成平台 SSE 输出

### 8.3 Streaming 协议

MVP 使用 SSE，事件类型固定为：

- `session_started`
- `assistant_delta`
- `tool_event`
- `final`
- `error`

保证目标：

- 用户能在流中拿到最终答案
- 用户能看到关键工具事件
- 即使 SDK 内部事件粒度变化，平台也维持稳定的外部协议

## 9. 权限与安全

### 9.1 工具优先级

1. Claude Agent SDK 原生工具
2. 外部系统交互时才考虑 MCP

### 9.2 MVP 策略

- 默认关闭 MCP
- 默认只传递原生工具白名单
- 当 `require_approval_for_write=true` 时，平台只允许保守的 `permission_mode`
- 上传文件名必须去路径、去危险字符
- 不回显密钥或敏感环境变量

## 10. 测试策略

实现必须先补失败测试，再写生产代码。

### 10.1 首批测试

- 配置加载：
  - 默认配置
  - `ENV` 覆盖
- 上传接口：
  - 正常上传
  - 扩展名非法
  - 文件超限
- SessionManager：
  - 创建映射
  - 更新映射
  - 查找不存在映射
- Chat 接口：
  - 首轮调用写入 `sdk_session_id`
  - 二轮调用自动 `resume`
  - `app_id` 与 `skill_name` 解析
  - 引用已上传文件

## 11. 交付标准

满足以下条件才算 MVP 完成：

- `/api/v1/health`、`/api/v1/upload`、`/api/v1/chat` 可运行
- 首轮和多轮对话都能正确建立/恢复 session
- Skill 能按标准目录加载
- 上传与对话职责严格分离
- 默认不依赖 Redis、MCP、Vertex AI 外部环境
- 关键路径测试通过
