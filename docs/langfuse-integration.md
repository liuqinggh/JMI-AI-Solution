# LangFuse 集成文档

## 简介

本项目已集成 [LangFuse](https://langfuse.com/) 作为 LLM 应用的可观测性和追踪平台。LangFuse 能够帮助你：

- 📊 追踪 Agent 执行过程中的所有 LLM 调用
- ⏱️ 监控延迟和性能指标
- 💰 分析 token 使用和成本
- 🔍 调试和优化 Agent 行为
- 📈 生成使用报告和分析

## 快速开始

### 1. 获取 LangFuse 密钥

#### 使用 LangFuse Cloud（推荐）

1. 访问 [https://cloud.langfuse.com/](https://cloud.langfuse.com/)
2. 注册账号并登录
3. 创建一个新项目
4. 在项目设置中获取 API 密钥（Public Key 和 Secret Key）

#### 自托管 LangFuse

参考 [LangFuse 自托管文档](https://langfuse.com/docs/deployment/self-host)

### 2. 配置环境变量

复制环境变量示例文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 LangFuse 密钥：

```bash
LANGFUSE_PUBLIC_KEY=lf_pk_your_public_key_here
LANGFUSE_SECRET_KEY=lf_sk_your_secret_key_here
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3. 启用 LangFuse

编辑 `conf/config.yaml`，将 `langfuse.enabled` 设置为 `true`：

```yaml
langfuse:
  enabled: true
  host: https://cloud.langfuse.com
```

### 4. 重启服务

```bash
python main.py
```

## 配置选项

LangFuse 支持以下配置方式（优先级从高到低）：

1. **环境变量**（推荐）
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`
   - `LANGFUSE_HOST`

2. **配置文件** `conf/config.yaml`

```yaml
langfuse:
  enabled: true  # 是否启用 LangFuse
  public_key: lf_pk_xxx  # 可选，推荐使用环境变量
  secret_key: lf_sk_xxx  # 可选，推荐使用环境变量
  host: https://cloud.langfuse.com  # LangFuse 服务器地址
```

## 追踪的数据

### 1. Trace（追踪）

每次 API 调用 `/v1/agent/messages` 都会创建一个 Trace，包含：

- **session_id**: 会话标识符
- **user_id**: 用户标识符（可选，通过表单传递）
- **metadata**: 元数据
  - `prompt_length`: 提示长度
  - `has_files`: 是否包含文件
  - `file_count`: 文件数量
  - `structured_output_profile`: 结构化输出配置
  - `final_answer_policy`: 最终答案策略
  - `model`: 使用的模型
  - `max_turns`: 最大轮次

### 2. Generation（生成）

Agent 执行完成时记录的生成事件：

- **name**: `agent_query_completion`
- **model**: Claude 模型名称
- **start_time**: 开始时间
- **end_time**: 结束时间
- **input**: 用户提示
- **output**: Agent 最终回答
- **metadata**: 执行元数据
  - `success`: 是否成功
  - `message_count`: SDK 消息数量
  - `assistant_turns`: 助手回复轮次
  - `structured_output_present`: 是否有结构化输出

### 3. Event（事件）

执行过程中的离散事件：

- `agent_execution_start`: Agent 开始执行
- `sdk_message_*`: SDK 消息事件（TaskStartedMessage, AssistantMessage, ResultMessage 等）
- `agent_execution_error`: 执行错误
- `api_error`: API 错误

### 4. Tags（标签）

根据场景自动添加标签：

- `new_session`: 新会话
- `session_continuation`: 会话续接
- `jmi_intake_call_checkout`: 使用 JMI 报案核对 profile
- `jmi_fresh_claim_doc_check`: 使用 JMI 材料检查 profile

## API 使用示例

### 基础调用

```bash
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=分析这个文件" \
  -F "files=@document.pdf"
```

### 指定用户 ID（用于追踪）

```bash
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=分析这个文件" \
  -F "user_id=user_12345" \
  -F "files=@document.pdf"
```

### 多轮对话（保持 session_id）

```bash
# 第一轮
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=你好" \
  -F "user_id=user_12345"

# 返回 {"session_id": "sess_abc123", ...}

# 第二轮（使用相同 session_id）
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=帮我分析一下" \
  -F "session_id=sess_abc123" \
  -F "user_id=user_12345"
```

## 在 LangFuse 控制台查看数据

1. 登录 [LangFuse Cloud](https://cloud.langfuse.com/)
2. 选择你的项目
3. 查看追踪数据：
   - **Traces**: 查看所有追踪记录
   - **Sessions**: 按会话查看多轮对话
   - **Users**: 按用户查看使用情况
   - **Analytics**: 查看统计分析和成本

## 性能影响

LangFuse 集成设计为低开销：

- ✅ 异步发送数据，不阻塞主流程
- ✅ 本地缓冲，批量上传
- ✅ 失败自动重试
- ✅ 可以随时禁用（设置 `enabled: false`）

在禁用状态下，所有 tracing 调用都是无操作（no-op），几乎无性能影响。

## 故障排查

### 1. Trace 没有出现在 LangFuse 控制台

检查：
- ✅ `langfuse.enabled` 是否设置为 `true`
- ✅ API 密钥是否正确
- ✅ 网络是否能访问 `LANGFUSE_HOST`
- ✅ 查看应用日志是否有 LangFuse 错误信息

### 2. "Failed to initialize LangFuse" 错误

- 检查 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY` 是否正确
- 检查 `LANGFUSE_HOST` 是否可访问
- 如果使用自托管实例，确认服务正常运行

### 3. 查看调试日志

在 Python 代码中启用调试日志：

```python
import logging
logging.getLogger("langfuse").setLevel(logging.DEBUG)
```

或者在启动时设置环境变量：

```bash
export LANGFUSE_DEBUG=1
python main.py
```

## 最佳实践

### 1. 使用环境变量存储密钥

❌ 不要将密钥硬编码在 `config.yaml` 中
✅ 使用环境变量或 `.env` 文件（确保 `.env` 在 `.gitignore` 中）

### 2. 为不同环境使用不同项目

- 开发环境：`dev-project`
- 测试环境：`staging-project`
- 生产环境：`production-project`

### 3. 添加有意义的 metadata

在调用 API 时，可以通过 metadata 添加额外上下文：

```python
# 在代码中可以扩展 metadata
tracer.log_event(
    name="custom_event",
    metadata={
        "environment": "production",
        "feature": "document_analysis",
        "document_type": "invoice",
    }
)
```

### 4. 定期审查追踪数据

- 识别性能瓶颈
- 优化 prompt 策略
- 监控成本趋势
- 发现异常模式

## 相关链接

- [LangFuse 官方文档](https://langfuse.com/docs)
- [LangFuse Python SDK](https://langfuse.com/docs/sdk/python)
- [LangFuse Cloud](https://cloud.langfuse.com/)
- [LangFuse GitHub](https://github.com/langfuse/langfuse)

## 扩展功能

### 自定义 Scoring（评分）

可以为 Trace 添加评分，用于质量评估：

```python
# 在代码中添加评分
tracer.score_trace(
    name="accuracy",
    value=0.95,
    comment="高准确率输出"
)
```

### 与其他工具集成

LangFuse 支持与多种工具集成：

- Langchain
- LlamaIndex
- OpenAI SDK
- Anthropic SDK

详见 [LangFuse 集成文档](https://langfuse.com/docs/integrations)

---

如有问题，请查看项目文档或联系开发团队。
