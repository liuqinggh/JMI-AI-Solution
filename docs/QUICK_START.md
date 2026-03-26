# 快速启动指南

## 更新内容

本次更新为项目添加了以下功能：

### 1. Vertex AI 支持 ✅

项目现已支持通过 Google Cloud Vertex AI 调用 Claude 模型。

**配置位置**: `conf/config.yaml`

```yaml
sdk:
  env:
    CLAUDE_CODE_USE_VERTEX: "1"
    GOOGLE_APPLICATION_CREDENTIALS: /Users/cd-la-067/.config/gcloud/application_default_credentials.json
    ANTHROPIC_VERTEX_PROJECT_ID: ai-model-487001
    CLOUD_ML_REGION: global
```

### 2. 新增接口

#### GET /
健康检查接口

```bash
curl http://localhost:8000/
```

#### GET /config
获取配置信息接口（显示当前 Provider、模型等）

```bash
curl http://localhost:8000/config
```

### 3. 增强的测试页面

访问 `http://localhost:8000/test`，新功能包括：

- ✅ 自动加载并显示当前配置信息（Provider、Model、Region 等）
- ✅ 配置信息视觉区分（Vertex AI 模式使用蓝色标识）
- ✅ 执行步骤查看器（可切换显示/隐藏）
- ✅ 更好的错误处理和状态提示
- ✅ 简化的结果显示（步骤信息可选查看）

---

## 快速开始

### 1. 启动服务

```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动服务
uvicorn src.api.routes:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 验证配置

```bash
# 检查服务状态
curl http://localhost:8000/

# 查看当前配置
curl http://localhost:8000/config
```

**预期输出（Vertex AI 模式）**:

```json
{
  "model": "claude-sonnet-4-5",
  "provider": "Vertex AI",
  "max_turns": 25,
  "permission_mode": "acceptEdits",
  "vertex_project_id": "ai-model-487001",
  "region": "global"
}
```

### 3. 测试对话

#### 方法 1: Web 界面（推荐）

1. 访问 http://localhost:8000/test
2. 页面顶部会显示当前配置（Vertex AI 模式会有蓝色标识）
3. 在 Prompt 框输入测试内容
4. 点击"发送请求"
5. 查看结果（可点击"显示步骤"查看详细执行过程）

#### 方法 2: cURL

```bash
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=你好，请用一句话介绍你自己"
```

#### 方法 3: Python 测试脚本

```bash
python test_vertex_config.py
```

---

## 测试场景

### 场景 1: 基础对话

```bash
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=请解释什么是 Vertex AI"
```

### 场景 2: 多轮对话

```bash
# 第一轮
RESPONSE=$(curl -s -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=请记住这个数字：42")

# 提取 session_id
SESSION_ID=$(echo $RESPONSE | jq -r '.session_id')

# 第二轮（使用 session_id）
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=我刚才让你记住的数字是什么？" \
  -F "session_id=$SESSION_ID"
```

### 场景 3: 文件上传

```bash
# 创建测试文件
echo "这是一个测试文档" > test.txt

# 上传并分析
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=请读取并总结这个文件的内容" \
  -F "files=@test.txt"
```

---

## 配置切换

### 切换到 Vertex AI 模式

编辑 `conf/config.yaml`，添加：

```yaml
sdk:
  env:
    CLAUDE_CODE_USE_VERTEX: "1"
    GOOGLE_APPLICATION_CREDENTIALS: /path/to/credentials.json
    ANTHROPIC_VERTEX_PROJECT_ID: your-project-id
    CLOUD_ML_REGION: global
```

### 切换到本地代理模式

编辑 `conf/config.yaml`，注释掉或删除 `env` 部分：

```yaml
sdk:
  base_url: http://localhost:4000
  api_key: sk-1234
  # env:  # 注释掉即可切换回本地代理
  #   CLAUDE_CODE_USE_VERTEX: "1"
  #   ...
```

重启服务后，访问 `/config` 查看配置是否已更改。

---

## 目录结构

```
agent-sdk-api-service/
├── conf/
│   └── config.yaml              # 配置文件（已更新支持 Vertex AI）
├── src/
│   ├── api/
│   │   ├── routes.py            # API 路由（新增健康检查和配置接口）
│   │   ├── models.py            # 数据模型（新增响应模型）
│   │   └── static/
│   │       └── test/
│   │           └── index.html   # 测试页面（增强功能）
│   ├── agent/
│   │   ├── executor.py          # Agent 执行器
│   │   └── options.py           # Agent 选项
│   ├── storage/
│   │   └── file_store.py        # 文件存储
│   └── config.py                # 配置加载
├── test_vertex_config.py        # Vertex AI 配置测试脚本（新增）
├── VERTEX_AI_SETUP.md           # Vertex AI 配置文档（新增）
├── API_REFERENCE.md             # API 参考文档（新增）
└── QUICK_START.md               # 本文件
```

---

## 监控和调试

### 查看日志

```bash
# 启动时会看到配置信息
uvicorn src.api.routes:app --host 0.0.0.0 --port 8000 --reload
```

### 检查 Vertex AI 认证

```bash
# 验证凭证文件
cat /Users/cd-la-067/.config/gcloud/application_default_credentials.json

# 测试认证
gcloud auth application-default print-access-token
```

### 调试模式

在 Web 测试页面：

1. 提交请求后，点击"显示步骤"
2. 查看完整的执行步骤和消息类型
3. 检查 `success` 字段判断执行状态

---

## 常见问题

### Q1: 配置页面显示 "Local Proxy" 但我想用 Vertex AI

**A**: 检查 `conf/config.yaml` 中 `sdk.env.CLAUDE_CODE_USE_VERTEX` 是否为 `"1"`（字符串）。

### Q2: Vertex AI 认证失败

**A**: 运行以下命令重新认证：

```bash
gcloud auth application-default login
```

### Q3: 想查看更详细的执行过程

**A**: 访问测试页面 `http://localhost:8000/test`，提交请求后点击"显示步骤"按钮。

### Q4: 如何验证使用的是 Vertex AI 而不是本地代理？

**A**: 访问 `http://localhost:8000/config`，检查响应中的 `provider` 字段：

- `"Vertex AI"` = 使用 Vertex AI
- `"Local Proxy"` = 使用本地代理

---

## 下一步

- 📖 阅读 [API Reference](./API_REFERENCE.md) 了解所有接口
- 🔧 查看 [Vertex AI Setup](./VERTEX_AI_SETUP.md) 深入了解 Vertex AI 配置
- 🧪 运行 `python test_vertex_config.py` 进行完整测试
- 🌐 在浏览器打开 `http://localhost:8000/test` 使用可视化界面

---

## 技术支持

遇到问题？检查：

1. 服务是否正常运行（`curl http://localhost:8000/`）
2. 配置是否正确（`curl http://localhost:8000/config`）
3. Vertex AI 认证是否有效（如使用 Vertex AI）
4. 查看服务日志输出

祝使用愉快！🚀
