# LangFuse 快速启动指南

## 当前状态

✅ LangFuse 已集成到项目中
✅ 配置文件已设置（`conf/config.yaml`）
⚠️ 当前状态：**禁用**（需要手动启用）

## 立即启用 LangFuse

### 方式 1: 修改配置文件（推荐用于测试）

编辑 `conf/config.yaml`：

```yaml
langfuse:
  enabled: true  # 改为 true
  public_key: pk-lf-71284a80-fc2c-4c8a-8c88-89e09d8464f9
  secret_key: sk-lf-4940feb5-03c7-4a5a-ad57-5703ffcdbd3a
  host: https://langfuse.dev.iglooinsure.com
```

### 方式 2: 使用环境变量（推荐用于生产）

```bash
export LANGFUSE_PUBLIC_KEY="pk-lf-71284a80-fc2c-4c8a-8c88-89e09d8464f9"
export LANGFUSE_SECRET_KEY="sk-lf-4940feb5-03c7-4a5a-ad57-5703ffcdbd3a"
export LANGFUSE_HOST="https://langfuse.dev.iglooinsure.com"
```

然后在配置文件中启用：
```yaml
langfuse:
  enabled: true
```

## 测试 LangFuse 集成

### 1. 运行测试脚本

```bash
uv run python scripts/test_langfuse.py
```

**如果 LangFuse 未启用**，你会看到：
```
⚠️  LangFuse 未启用
   要启用 LangFuse，请:
   1. 在 conf/config.yaml 中设置 langfuse.enabled: true
   2. 确保配置了正确的 public_key 和 secret_key
```

**如果 LangFuse 已启用**，你会看到：
```
✅ 所有测试通过！
📊 请访问 https://langfuse.dev.iglooinsure.com 查看追踪数据
```

### 2. 启动服务

```bash
uv run python main.py
```

### 3. 测试 API 调用

```bash
# 基础调用
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=你好，请介绍一下自己"

# 带用户 ID 的调用（用于追踪）
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=你好" \
  -F "user_id=test_user_123"

# 多轮对话
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=你好" \
  -F "user_id=test_user_123" | jq -r '.session_id'

# 使用返回的 session_id 继续对话
curl -X POST http://localhost:8000/v1/agent/messages \
  -F "prompt=继续聊天" \
  -F "session_id=<返回的session_id>" \
  -F "user_id=test_user_123"
```

### 4. 查看追踪数据

访问 https://langfuse.dev.iglooinsure.com

1. **Traces** - 查看所有 API 调用
2. **Sessions** - 查看多轮对话
3. **Users** - 按用户查看使用情况
4. **Analytics** - 查看统计和成本分析

## 追踪的数据内容

每次 API 调用会记录：

### Trace 级别
- `session_id` - 会话标识
- `user_id` - 用户标识（如果提供）
- `metadata` - 请求元数据
  - `prompt_length` - 提示长度
  - `file_count` - 上传文件数
  - `structured_output_profile` - 使用的输出 profile
  - `model` - 使用的模型

### Generation 级别
- `name`: `agent_query_completion`
- `model`: 模型名称
- `start_time` / `end_time` - 执行时间
- `input` - 用户提示
- `output` - Agent 回复
- `metadata` - 执行结果
  - `success` - 是否成功
  - `message_count` - SDK 消息数
  - `assistant_turns` - 助手回复轮次

### Event 级别
- `agent_execution_start` - 开始执行
- `sdk_message_*` - SDK 消息事件
- `agent_execution_error` - 执行错误
- `api_error` - API 错误

### Tags（标签）
- `new_session` - 新会话
- `session_continuation` - 会话续接
- `jmi_intake_call_checkout` - JMI 报案核对
- `jmi_fresh_claim_doc_check` - JMI 材料检查

## 性能影响

- **禁用时**: 几乎无性能影响（所有调用都是 no-op）
- **启用时**:
  - ✅ 异步发送，不阻塞主流程
  - ✅ 本地缓冲，批量上传
  - ✅ 自动重试机制
  - ⚠️ 轻微内存开销（用于缓冲）

## 常见问题

### Q: 为什么 Trace 没有出现在控制台？

检查：
1. `langfuse.enabled` 是否为 `true`
2. API 密钥是否正确
3. 网络能否访问 `https://langfuse.dev.iglooinsure.com`
4. 查看应用日志是否有错误

### Q: 如何临时禁用 LangFuse？

方式 1 - 配置文件：
```yaml
langfuse:
  enabled: false
```

方式 2 - 环境变量：
```bash
# 不设置 LANGFUSE_PUBLIC_KEY 和 LANGFUSE_SECRET_KEY
# 或者在配置中设置 enabled: false
```

### Q: 如何查看 LangFuse 调试日志？

在代码中添加：
```python
import logging
logging.getLogger("langfuse").setLevel(logging.DEBUG)
```

或设置环境变量：
```bash
export LANGFUSE_DEBUG=1
```

## 下一步

1. ✅ 启用 LangFuse（修改 `conf/config.yaml`）
2. ✅ 运行测试脚本验证集成
3. ✅ 访问控制台查看数据
4. 📊 设置告警和监控
5. 📈 分析使用模式和成本

---

详细文档：[docs/langfuse-integration.md](./langfuse-integration.md)
