# CLAUDE.md - FastAPI + Claude Agent SDK 智能体平台

这是一个通过 FastAPI 暴露 Claude Agent SDK 驱动的多技能智能体平台，支持文件上传、会话管理、权限控制和 SSE 流式响应。

## 项目结构地图（实际代码结构）

```
JMI-AI-Solution/
├── app/                          # 主应用代码
│   ├── main.py                   # FastAPI 应用入口（应用工厂）
│   ├── core/                     # 核心功能模块
│   │   ├── config.py             # 统一配置管理（YAML + 环境变量）
│   │   ├── permissions.py        # 权限解析与控制
│   │   ├── session_manager.py    # 会话映射管理
│   │   └── session_id.py         # 会话 ID 生成与验证
│   ├── agents/                   # Claude Agent SDK 客户端
│   │   └── client.py             # SDK 封装与流式事件处理
│   ├── api/                      # REST API 路由（平级组织）
│   │   ├── __init__.py           # 路由注册中心（/api/v1 前缀）
│   │   ├── chat.py               # POST /chat - 聊天与 Agent 执行
│   │   ├── upload.py             # POST /upload - 文件上传
│   │   └── health.py             # GET /health - 健康检查
│   ├── models/                   # Pydantic 数据模型
│   │   ├── chat.py               # ChatRequest 模型
│   │   ├── session.py            # SessionMapping, PermissionProfile
│   │   ├── upload.py             # UploadedFile 模型
│   │   └── app.py                # RegisteredApp 模型
│   ├── services/                 # 业务逻辑服务层
│   │   ├── skill_loader.py       # 技能加载（读取 .claude/skills/）
│   │   ├── upload_service.py     # 文件上传与存储管理
│   │   ├── workspace_service.py  # 工作区准备与消息组装
│   │   └── app_registry.py       # 应用注册表查询
│   ├── storage/                  # 文件存储（内容寻址存储）
│   └── tracing/                  # 追踪（Langfuse 集成）
├── .claude/                      # Claude 配置目录
│   ├── skills/                   # 技能定义（Skill Prompt）
│   │   ├── jmi-fresh-claim-doc-check/SKILL.md
│   │   ├── jmi-intake-call-checkout/SKILL.md
│   │   ├── document-ocr-ai/SKILL.md
│   │   ├── image-by-intent/SKILL.md
│   │   └── local-rag/SKILL.md
│   └── rules/                    # 开发规范（Claude Code 规则）
│       ├── claude_agent_sdk.md   # SDK 使用规范
│       ├── fastapi_best_practices.md # FastAPI 最佳实践
│       ├── code_style_and_security.md # 代码风格与安全
│       └── prompt_engineering.md # 提示工程规范
├── conf/                         # 配置文件
│   ├── config.yaml               # 主配置（应用、技能、权限）
│   └── config.example.yaml       # 配置示例
├── docs/                         # 项目文档
│   ├── QUICK_START.md            # 快速开始
│   ├── FILE_UPLOAD_DESIGN.md     # 文件上传架构设计
│   ├── FILE_UPLOAD_IMPLEMENTATION.md # 实现细节
│   ├── FILE_UPLOAD_MIGRATION.md  # 迁移指南
│   ├── VERTEX_AI_SETUP.md        # Vertex AI 配置
│   └── langfuse-integration.md   # Langfuse 追踪集成
├── tests/                        # 测试文件
└── pyproject.toml                # 项目依赖（Claude Agent SDK >= 0.1.49）
```

## 核心架构说明

### 1. 请求处理流程

```
客户端请求 
  → FastAPI 路由（app/api/*.py）
  → 服务层（app/services/）
  → Agent 客户端（app/agents/client.py）
  → Claude Agent SDK（query()）
  → SSE 流式返回
```

### 2. 技能系统

- **技能定义**: `.claude/skills/{skill_name}/SKILL.md`
- **加载机制**: `SkillLoader` 读取 SKILL.md 作为系统提示
- **技能注册**: 通过 `conf/config.yaml` 中的 `apps` 配置关联

### 3. 会话管理

- **业务会话 ID**: 由客户端提供，用于关联同一对话
- **SDK 会话 ID**: 由 Claude Agent SDK 生成，用于恢复上下文
- **映射存储**: `SessionManager` 持久化业务 ID → SDK ID 映射

### 4. 文件上传

- **上传端点**: `POST /api/v1/upload`
- **存储服务**: `UploadService` 管理文件存储
- **工作区服务**: `WorkspaceService` 准备 Agent 运行时文件环境

## 核心硬规则（始终遵守）

1. **优先使用 Claude Agent SDK 原生能力**：通过 `query()` 执行，所有操作异步
2. **工具严格控制权限**：使用 `permission_mode` 和 `allowed_tools` 限制
3. **FastAPI 接口使用 Pydantic v2**：类型提示 + Streaming 支持
4. **代码风格统一**：ruff format + 全面类型注解
5. **安全第一**：用户输入验证 + 会话隔离 + 文件沙箱

## 快速开始

### 启动服务

```bash
# 开发模式（自动重载）
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或直接运行（如果 app.main 包含启动逻辑）
python -m app.main
```

### API 端点

| 端点 | 方法 | 说明 |
|-----|------|-----|
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/upload` | POST | 文件上传 |
| `/api/v1/chat` | POST | 聊天与 Agent 执行（SSE 流式） |

### 环境配置

```bash
# 1. 复制配置示例（如果需要）
cp conf/config.example.yaml conf/config.yaml

# 2. 编辑配置文件
vim conf/config.yaml

# 3. 设置环境变量（可选，用于覆盖配置文件）
# Vertex AI 配置
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export ANTHROPIC_VERTEX_PROJECT_ID=your-project-id
export CLOUD_ML_REGION=global

# 或使用 Anthropic API
export ANTHROPIC_API_KEY=sk-ant-...

# Langfuse 追踪（可选）
export LANGFUSE_PUBLIC_KEY=lf_pk_...
export LANGFUSE_SECRET_KEY=lf_sk_...
```

### 配置文件结构（conf/config.yaml）

```yaml
app:                          # 应用基础配置
  name: Claude Agent Platform
  version: 0.1.0
  environment: dev
  host: 0.0.0.0
  port: 8000

claude:                       # Claude Agent SDK 配置
  model: claude-sonnet-4-5    # 模型名称
  base_url: http://localhost:4000  # API 端点（可选）
  api_key: sk-1234            # API Key（建议通过环境变量设置）
  permission_mode: default    # 权限模式：default / strict / permissive
  default_allowed_tools:      # 默认允许的工具列表
    - Read
    - Write
    - Edit
    - MultiEdit
    - Glob
    - Grep
    - LS
  mcp_enabled: false          # 是否启用 MCP
  env:                        # SDK 环境变量
    CLAUDE_CODE_USE_VERTEX: "1"
    CLOUD_ML_REGION: global

session:                      # 会话管理配置
  storage_dir: runtime/sessions
  mapping_ttl_seconds: 604800 # 7天

upload:                       # 文件上传配置
  temp_dir: uploads/temp
  max_file_size_mb: 20
  allowed_extensions:
    - .txt
    - .md
    - .json
    - .csv
    - .pdf

security:                     # 安全配置
  can_use_tool_hook: true
  require_approval_for_write: true

apps:                         # 应用注册（技能与权限绑定）
  default:
    skill_name: fastapi-dev
    cwd: .
    permission_mode: default
    allowed_tools: []
```

## 文档索引

### 核心文档
- **快速开始**: `docs/QUICK_START.md`
- **文件上传设计**: `docs/FILE_UPLOAD_DESIGN.md`
- **文件上传实现**: `docs/FILE_UPLOAD_IMPLEMENTATION.md`
- **文件上传迁移指南**: `docs/FILE_UPLOAD_MIGRATION.md` ⭐️ 重要
- **Vertex AI 配置**: `docs/VERTEX_AI_SETUP.md`
- **Langfuse 集成**: `docs/langfuse-integration.md`
- **Langfuse 快速开始**: `docs/langfuse-quickstart.md`
- **存储优化**: `docs/storage-optimization.md`

### 技术方案文档（中文）
- **Claude Agent SDK + SKILLs 场景下的文件处理**: `docs/Claude-Agent-SDK+SKILLs场景下的文件处理方案.md`
- **Claude Agent SDK 输出固定 JSON 的方案**: `docs/claude-agent-SDK输出固定的json的方案.md`
- **SDK Structured Outputs 实现总结**: `docs/实现总结-SDK-Structured-Outputs.md`
- **需求文档**: `docs/需求.md`

## 开发规范

需要专项细节时，主动阅读 `.claude/rules/` 目录下的对应文件：

- **claude_agent_sdk.md** - SDK 使用、工具选择、权限控制
- **fastapi_best_practices.md** - API 设计、路由组织、依赖注入
- **code_style_and_security.md** - 代码风格、安全规则、配置管理
- **prompt_engineering.md** - 提示工程、系统提示、输出控制

## 代码格式化

```bash
# 使用 ruff 格式化代码
ruff format .

# 使用 ruff 检查代码
ruff check .
```

## 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_api_v1.py -v

# 查看覆盖率
pytest --cov=app tests/
```

## 常见任务

### 添加新技能

1. 创建技能目录：`.claude/skills/{skill_name}/`
2. 编写技能提示：`.claude/skills/{skill_name}/SKILL.md`
3. 在 `conf/config.yaml` 的 `apps` 部分注册
4. 测试：`POST /api/v1/chat` 指定 `skill_name`

### 修改权限配置

编辑 `app/core/permissions.py` 和 `conf/config.yaml` 中的：
- `permission_mode`: `default`, `strict`, `permissive`
- `allowed_tools`: 允许的工具列表

### 调试流式响应

```bash
# 使用 curl 测试 SSE
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "business_session_id": "test-123",
    "skill_name": "document-ocr-ai"
  }'
```

## 技术栈

- **Web 框架**: FastAPI 0.115+
- **Agent SDK**: Claude Agent SDK 0.1.49+
- **数据验证**: Pydantic v2
- **配置管理**: PyYAML + python-dotenv
- **流式响应**: sse-starlette
- **追踪**: Langfuse 4.0+
- **代码质量**: ruff, black, pytest
