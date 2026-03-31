# CLAUDE.md - FastAPI + Claude Agent SDK 智能体项目

这是一个通过 FastAPI 暴露 Claude Agent SDK 驱动的智能体应用，支持 Tool Use、MCP 和复杂多步任务。

## 项目结构地图

```
JMI-AI-Solution/
├── app/                          # 主应用代码
│   ├── main.py                   # FastAPI 入口
│   ├── config.py                 # 统一配置管理
│   ├── core/                     # 核心模块
│   │   ├── security.py           # API Key 验证、权限控制
│   │   └── logging.py            # 日志配置与工具
│   ├── agents/                   # Agent 执行器
│   │   ├── executor.py           # 核心执行逻辑
│   │   ├── options.py            # SDK 选项构建
│   │   ├── schema_registry.py    # 结构化输出 Schema 注册
│   │   └── tools/                # 自定义 MCP 工具
│   │       ├── example_tool.py   # 示例工具
│   │       └── README.md         # 工具开发指南
│   ├── api/                      # REST API
│   │   ├── app.py                # FastAPI 应用工厂
│   │   └── v1/                   # API v1 版本
│   │       ├── deps.py           # 依赖注入
│   │       └── endpoints/        # 路由端点
│   │           ├── agents.py     # Agent 执行端点
│   │           ├── files.py      # 文件上传端点（新）
│   │           ├── health.py     # 健康检查
│   │           └── test.py       # 测试页面
│   ├── schemas/                  # Pydantic 数据模型
│   │   ├── agent.py              # Agent 响应模型
│   │   ├── file.py               # 文件上传模型（新）
│   │   ├── structured.py         # 结构化输出模型
│   │   └── health.py             # 健康检查模型
│   ├── services/                 # 业务服务层（新）
│   │   ├── upload_batch_service.py      # 批次上传服务
│   │   └── session_workspace_service.py # 会话工作区服务
│   └── tracing/                  # 追踪与监控
│       └── langfuse_tracer.py    # Langfuse 集成
├── conf/                         # 配置文件
│   ├── config.yaml               # 主配置
│   └── config.example.yaml       # 配置示例
├── docs/                         # 项目文档
│   ├── QUICK_START.md            # 快速开始
│   ├── API_REFERENCE.md          # API 参考
│   ├── FILE_UPLOAD_DESIGN.md     # 文件上传设计
│   └── VERTEX_AI_SETUP.md        # Vertex AI 配置
├── tests/                        # 测试文件
├── .claude/rules/                # Claude Code 规则
│   ├── claude_agent_sdk.md       # SDK 使用规范
│   ├── fastapi_best_practices.md # FastAPI 最佳实践
│   ├── code_style_and_security.md# 代码风格与安全
│   └── prompt_engineering.md     # 提示工程规范
└── main.py                       # 向后兼容入口
```

## 核心硬规则（始终遵守）

1. **优先使用 Claude Agent SDK 原生能力**，所有操作异步
2. **工具严格控制权限**，危险操作必须 sandbox
3. **FastAPI 接口必须使用 Pydantic v2** + 类型提示 + Streaming 支持
4. **代码风格统一**（ruff + black），全面类型注解
5. **安全第一**：用户输入验证 + API Key 保护

## 快速开始

### 启动服务

```bash
# 开发模式（自动重载）
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或直接运行
python -m app.main
```

### API 端点

- `GET /api/v1/health` - 健康检查
- `GET /api/v1/config` - 配置信息
- `POST /api/v1/agent/messages` - 执行 Agent 任务
- `GET /api/v1/test` - 测试页面

### 环境配置

```bash
# 复制配置示例
cp conf/config.example.yaml conf/config.yaml

# 设置 API Key（可选，用于认证）
export AGENT_API_KEY=your_secret_key

# Langfuse 追踪（可选）
export LANGFUSE_PUBLIC_KEY=lf_pk_...
export LANGFUSE_SECRET_KEY=lf_sk_...
```

## 文档索引

- **快速开始**: `docs/QUICK_START.md`
- **API 参考**: `docs/API_REFERENCE.md`
- **文件上传设计**: `docs/FILE_UPLOAD_DESIGN.md`
- **Vertex AI 配置**: `docs/VERTEX_AI_SETUP.md`
- **Langfuse 集成**: `LANGFUSE_INTEGRATION.md`
- **工具开发指南**: `app/agents/tools/README.md`

## 开发规范

需要专项细节时，主动阅读 `.claude/rules/` 目录下的对应文件：

- **claude_agent_sdk.md** - SDK 使用、MCP 工具、权限控制
- **fastapi_best_practices.md** - API 设计、路由组织、依赖注入
- **code_style_and_security.md** - 代码风格、安全规则、配置管理
- **prompt_engineering.md** - 提示工程、系统提示、输出控制

## 代码格式化

```bash
# 使用 ruff 格式化代码
ruff format .

# 使用 ruff 检查代码
ruff check .

# 使用 black 格式化（备选）
black .
```

## 测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_routes.py -v
```