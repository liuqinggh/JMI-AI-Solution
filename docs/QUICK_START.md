# 快速启动指南

本文档帮助你快速启动并测试 Claude Agent Platform。

## 前置要求

- Python 3.11+
- 虚拟环境已创建并激活
- 依赖已安装（`uv sync` 或 `pip install -e .`）

## 1. 配置服务

### 选项 A: 使用 Vertex AI（推荐用于生产）

1. 配置 Google Cloud 凭证：

```bash
# 方法 1: Application Default Credentials
gcloud auth application-default login

# 方法 2: 使用服务账号
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

2. 编辑 `conf/config.yaml`：

```yaml
claude:
  model: claude-sonnet-4-5
  env:
    CLAUDE_CODE_USE_VERTEX: "1"
    ANTHROPIC_VERTEX_PROJECT_ID: your-project-id
    CLOUD_ML_REGION: global
```

详细配置见 [VERTEX_AI_SETUP.md](./VERTEX_AI_SETUP.md)。

### 选项 B: 使用 Anthropic API

1. 设置 API Key：

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

2. 编辑 `conf/config.yaml`：

```yaml
claude:
  model: claude-sonnet-4-5
  api_key: ${ANTHROPIC_API_KEY}  # 或直接填写（不推荐）
  # 移除或注释掉 env.CLAUDE_CODE_USE_VERTEX
```

### 选项 C: 使用本地代理（开发调试）

编辑 `conf/config.yaml`：

```yaml
claude:
  model: claude-sonnet-4-5
  base_url: http://localhost:4000
  api_key: sk-1234
```

## 2. 启动服务

```bash
# 方法 1: 使用 uvicorn（推荐用于开发）
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 方法 2: 直接运行（如果 app.main 包含启动逻辑）
python -m app.main

# 方法 3: 使用生产服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

服务启动后，访问 http://localhost:8000

## 3. 验证服务

### 健康检查

```bash
curl http://localhost:8000/api/v1/health
```

**预期输出**：

```json
{
  "status": "healthy",
  "service": "Claude Agent Platform",
  "version": "0.1.0"
}
```

## 4. 测试 API

### 4.1 文件上传

```bash
# 创建测试文件
echo "这是一个测试文档" > test.txt

# 上传文件
curl -X POST http://localhost:8000/api/v1/upload \
  -F "files=@test.txt" \
  | jq

# 上传多个文件
curl -X POST http://localhost:8000/api/v1/upload \
  -F "files=@test1.txt" \
  -F "files=@test2.pdf" \
  | jq
```

**预期输出**：

```json
{
  "files": [
    {
      "file_id": "abc123...",
      "filename": "test.txt",
      "size": 123,
      "content_type": "text/plain"
    }
  ]
}
```

### 4.2 简单对话（SSE 流式响应）

```bash
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好，请用一句话介绍你自己",
    "business_session_id": "test-session-001",
    "skill_name": "document-ocr-ai"
  }'
```

**响应格式**（Server-Sent Events）：

```
event: session_started
data: {"sdk_session_id": "abc123..."}

event: assistant_delta
data: {"text": "你好！我是 Claude..."}

event: final
data: {"final_answer": "你好！我是 Claude，一个 AI 助手。", "sdk_session_id": "abc123..."}
```

### 4.3 带文件的对话

```bash
# 1. 上传文件，获取 file_id
FILE_ID=$(curl -s -X POST http://localhost:8000/api/v1/upload \
  -F "files=@test.txt" | jq -r '.files[0].file_id')

# 2. 发送带文件的聊天请求
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"请总结这个文件的内容\",
    \"business_session_id\": \"test-session-002\",
    \"skill_name\": \"document-ocr-ai\",
    \"file_ids\": [\"$FILE_ID\"]
  }"
```

### 4.4 多轮对话

```bash
# 第一轮：使用固定的 business_session_id
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "请记住这个数字：42",
    "business_session_id": "multi-turn-session",
    "skill_name": "document-ocr-ai"
  }'

# 第二轮：使用相同的 business_session_id
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "我刚才让你记住的数字是什么？",
    "business_session_id": "multi-turn-session",
    "skill_name": "document-ocr-ai"
  }'
```

## 5. 可用技能

项目内置以下技能（位于 `.claude/skills/`）：

| 技能名称 | 说明 | 使用场景 |
|---------|------|---------|
| `document-ocr-ai` | 文档 OCR 和分析 | 处理图片、PDF 文档 |
| `jmi-fresh-claim-doc-check` | JMI 新鲜理赔文档检查 | 理赔文档验证 |
| `jmi-intake-call-checkout` | JMI 接入电话检查 | 电话记录分析 |
| `image-by-intent` | 图像意图识别 | 图像分类和理解 |
| `local-rag` | 本地 RAG 检索 | 文档检索增强生成 |

### 使用指定技能

```bash
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "分析这个图片",
    "business_session_id": "image-test",
    "skill_name": "image-by-intent"
  }'
```

## 6. 权限配置

### 查看默认权限

编辑 `conf/config.yaml`：

```yaml
claude:
  permission_mode: default  # default / strict / permissive
  default_allowed_tools:
    - Read
    - Write
    - Edit
    - MultiEdit
    - Glob
    - Grep
    - LS
```

### 按应用配置权限

```yaml
apps:
  my-app:
    skill_name: document-ocr-ai
    cwd: .
    permission_mode: strict
    allowed_tools:
      - Read
      - Glob
      - Grep
```

使用：

```bash
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "读取文件",
    "business_session_id": "test",
    "app_id": "my-app"
  }'
```

## 7. 监控和调试

### 查看运行时日志

```bash
# 启动时会显示配置信息
python -m uvicorn app.main:app --reload --log-level debug
```

### 检查会话存储

```bash
# 查看存储的会话映射
ls -la runtime/sessions/

# 查看上传的文件
ls -la uploads/temp/
```

### Vertex AI 调试

```bash
# 验证凭证
gcloud auth application-default print-access-token

# 测试 API 访问
curl -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  https://global-aiplatform.googleapis.com/v1/projects/YOUR_PROJECT/locations/global/publishers/anthropic/models/claude-sonnet-4-5:streamRawPredict
```

## 8. 常见问题

### Q1: 提示 "Skill 'xxx' not found"

**A**: 检查 `.claude/skills/{skill_name}/SKILL.md` 文件是否存在。

### Q2: SSE 响应没有数据

**A**: 
1. 检查 API Key 或 Vertex AI 配置是否正确
2. 查看服务日志中的错误信息
3. 确认 skill_name 或 app_id 配置正确

### Q3: 文件上传失败

**A**: 
1. 检查文件大小是否超过 `upload.max_file_size_mb`（默认 20MB）
2. 检查文件扩展名是否在 `upload.allowed_extensions` 中
3. 确认 `uploads/temp/` 目录有写入权限

### Q4: 多轮对话上下文丢失

**A**: 
1. 确保每轮对话使用相同的 `business_session_id`
2. 检查 `runtime/sessions/` 目录中的映射文件
3. 会话 TTL 默认 7 天，超期会自动清理

## 9. 下一步

- 📖 阅读 [CLAUDE.md](../CLAUDE.md) 了解项目架构
- 🔧 查看 [FILE_UPLOAD_IMPLEMENTATION.md](./FILE_UPLOAD_IMPLEMENTATION.md) 了解文件处理机制
- 📚 阅读 `.claude/rules/` 了解开发规范
- 🧪 运行 `pytest tests/` 执行完整测试

## 10. 生产部署清单

- [ ] 通过环境变量设置敏感配置（API Key、凭证等）
- [ ] 设置 `permission_mode: strict`
- [ ] 限制 `allowed_tools`（禁用 Bash、Write）
- [ ] 配置 `require_approval_for_write: true`
- [ ] 设置合理的 `max_turns`（如 12）
- [ ] 配置日志级别（`logging.level: INFO` 或 `WARNING`）
- [ ] 使用生产级 WSGI 服务器（如 gunicorn + uvicorn worker）
- [ ] 添加反向代理（Nginx）和 HTTPS
- [ ] 配置监控和告警（如 Prometheus + Grafana）
- [ ] 定期清理临时文件和过期会话

---

祝使用愉快！🚀

如有问题，请查看 [CLAUDE.md](../CLAUDE.md) 或提交 Issue。
