# Vertex AI 配置说明

本项目已配置支持通过 Google Vertex AI 调用 Claude 模型。

## 前提条件

1. **GCP 项目设置**
   - 确保您有一个启用了 Vertex AI API 的 GCP 项目
   - 项目 ID: `ai-model-487001`

2. **身份验证凭证**
   - 需要配置 Application Default Credentials (ADC)
   - 凭证文件路径: `/Users/cd-la-067/.config/gcloud/application_default_credentials.json`

## 配置说明

### 1. 环境变量配置

项目已在 `conf/config.yaml` 中配置了以下 Vertex AI 环境变量：

```yaml
sdk:
  env:
    CLAUDE_CODE_USE_VERTEX: "1"                    # 启用 Vertex AI 模式
    GOOGLE_APPLICATION_CREDENTIALS: /Users/cd-la-067/.config/gcloud/application_default_credentials.json
    ANTHROPIC_VERTEX_PROJECT_ID: ai-model-487001  # GCP 项目 ID
    CLOUD_ML_REGION: global                        # Vertex AI 区域
```

### 2. 配置文件说明

- `CLAUDE_CODE_USE_VERTEX`: 设为 "1" 启用 Vertex AI 模式
- `GOOGLE_APPLICATION_CREDENTIALS`: ADC 凭证文件的完整路径
- `ANTHROPIC_VERTEX_PROJECT_ID`: 您的 GCP 项目 ID
- `CLOUD_ML_REGION`: Vertex AI 区域（默认 global，也可以使用 us-east5 等）

### 3. 代码工作原理

项目中的 `src/config.py` 和 `src/agent/options.py` 已经实现了托管 provider 的支持：

```python
def _use_managed_provider(env: dict[str, str]) -> bool:
    keys = (
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_FOUNDRY",
    )
    return any(_is_truthy_env(os.environ.get(key) or env.get(key)) for key in keys)
```

当检测到 `CLAUDE_CODE_USE_VERTEX=1` 时，系统会：
- **不** 注入本地代理的 `base_url` 和 `api_key`
- 使用配置的环境变量传递给 Claude Agent SDK
- SDK 会自动通过 Vertex AI 调用 Claude 模型

## 测试配置

运行测试脚本验证配置：

```bash
# 激活虚拟环境
source .venv/bin/activate

# 运行测试
python test_vertex_config.py
```

测试脚本会：
1. 加载配置文件
2. 验证环境变量设置
3. 检查凭证文件是否存在
4. 执行一个简单的对话测试

## 启动服务

```bash
# 激活虚拟环境
source .venv/bin/activate

# 启动 FastAPI 服务
uvicorn src.api.routes:app --host 0.0.0.0 --port 8000 --reload
```

服务会自动使用 Vertex AI 配置，无需额外设置环境变量（已在 config.yaml 中配置）。

## 切换回本地代理模式

如果需要切换回本地代理模式（如 OpenAI 兼容的本地服务），只需：

1. 编辑 `conf/config.yaml`
2. 注释掉或删除 `sdk.env` 部分：

```yaml
sdk:
  base_url: http://localhost:4000
  api_key: sk-1234
  model: claude-sonnet-4-6
  # env:  # 注释掉这部分以使用本地代理
  #   CLAUDE_CODE_USE_VERTEX: "1"
  #   ...
```

## 故障排查

### 1. 凭证文件不存在

如果提示凭证文件不存在，运行：

```bash
gcloud auth application-default login
```

这会创建 ADC 凭证文件。

### 2. Vertex AI API 未启用

```bash
gcloud services enable aiplatform.googleapis.com --project=ai-model-487001
```

### 3. 权限不足

确保您的 GCP 账号有 Vertex AI User 权限：

```bash
gcloud projects add-iam-policy-binding ai-model-487001 \
    --member="user:YOUR_EMAIL" \
    --role="roles/aiplatform.user"
```

## 参考资料

- [Claude on Vertex AI Documentation](https://docs.anthropic.com/en/api/claude-on-vertex-ai)
- [Google Cloud Authentication](https://cloud.google.com/docs/authentication)
- [Vertex AI Regions](https://cloud.google.com/vertex-ai/docs/general/locations)
