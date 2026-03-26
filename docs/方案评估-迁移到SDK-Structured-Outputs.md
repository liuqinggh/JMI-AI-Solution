# 方案评估：迁移到 SDK Structured Outputs

## 当前实现（后处理方案）

### 架构
```
用户请求 → FastAPI → Agent SDK → Skill (SKILL.md 提示输出 JSON)
                                     ↓
                          Assistant 自然语言回复（含 JSON 字符串）
                                     ↓
                          后处理层：extract_first_json_value()
                                     ↓
                          剥离围栏：strip_markdown_json_fence()
                                     ↓
                          Pydantic 校验：JmiIntakeCallCheckoutOutput.model_validate()
                                     ↓
                          返回：structured_output 或 structured_error
```

### 核心代码位置
- `src/api/jmi_intake_checkout_output.py:119-133` - 手动解析 JSON
- `src/api/jmi_fresh_claim_doc_check_output.py:104-119` - 手动解析 JSON
- `src/api/routes.py:101-127` - 后处理调用
- `.claude/skills/jmi-intake-call-checkout/SKILL.md:8-13` - 靠 Prompt 约束输出

### 存在的问题

❌ **可靠性问题**
- 模型可能在 JSON 前后添加说明文字（需要正则提取）
- JSON 可能格式错误（缺少逗号、引号不匹配）
- 字段名可能拼写错误（人工校验成本高）

❌ **维护成本高**
- 需要维护复杂的后处理代码（围栏剥离、JSON 提取、异常处理）
- SKILL.md 中的输出约束难以强制执行（模型可能忽略）
- 每个 Skill 都需要重复实现解析逻辑

❌ **未利用 SDK 能力**
- Claude Agent SDK 已原生支持 Structured Outputs（需要模型 `claude-sonnet-4-5` 及以上）
- 当前实现绕过了 SDK 的结构化输出能力

## 推荐方案：SDK Structured Outputs

### 参考文档方案（第一种）

使用 `ClaudeAgentOptions.output_format` 配置：

```python
output_format = {
    "type": "json_schema",
    "schema": JmiIntakeCallCheckoutOutput.model_json_schema()
}

options = ClaudeAgentOptions(
    model="claude-sonnet-4-5",
    output_format=output_format,  # SDK 强制输出符合 Schema
    # ...
)

async for msg in query(prompt=prompt, options=options):
    if msg.get("type") == "result" and "structured_output" in msg:
        result = msg["structured_output"]  # 已校验的 dict
```

### 迁移后架构

```
用户请求 → FastAPI → 根据 structured_output_profile 选择 Schema
                          ↓
                   构建 output_format = {"type": "json_schema", "schema": ...}
                          ↓
                   Agent SDK (options.output_format) → 模型直接输出符合 Schema 的 JSON
                          ↓
                   msg["structured_output"] → 已校验的 dict（无需后处理）
                          ↓
                   返回：structured_output
```

### 优势对比

| 维度 | 当前方案（后处理） | SDK Structured Outputs |
|------|-------------------|------------------------|
| **可靠性** | 依赖 Prompt + 正则解析，容错复杂 | SDK 强制输出符合 Schema，100% 保证 |
| **代码量** | ~150 行后处理代码 | ~30 行 Schema 映射 |
| **维护成本** | 每个 Skill 需实现解析逻辑 | 统一 Schema 映射表，复用性高 |
| **性能** | 需解析整个回复文本 | SDK 直接返回结构化数据 |
| **新增 Skill** | 需添加 Parser + Pydantic + SKILL.md 约束 | 仅需添加 Pydantic Model + 映射关系 |
| **调试体验** | 后处理失败需人工排查 JSON 格式 | SDK 自动校验，错误信息清晰 |

## 实施方案

### 1. Schema 映射表（已具备基础）

项目已有 `ALLOWED_STRUCTURED_OUTPUT_PROFILES` 和 Pydantic 模型，只需扩展：

```python
# src/agent/schema_registry.py (新建)
from src.api.jmi_intake_checkout_output import JmiIntakeCallCheckoutOutput
from src.api.jmi_fresh_claim_doc_check_output import JmiFreshClaimDocCheckOutput

SCHEMA_MAP = {
    "jmi_intake_call_checkout": JmiIntakeCallCheckoutOutput,
    "jmi_fresh_claim_doc_check": JmiFreshClaimDocCheckOutput,
}

def get_output_format(profile: str | None) -> dict | None:
    """根据 structured_output_profile 动态生成 output_format"""
    if not profile:
        return None
    schema_model = SCHEMA_MAP.get(profile)
    if not schema_model:
        return None
    return {
        "type": "json_schema",
        "schema": schema_model.model_json_schema()
    }
```

### 2. 修改 `build_agent_options`

在 `src/agent/options.py` 中添加 `output_format` 参数：

```python
def build_agent_options(
    config: AppConfig,
    cwd: str | Path,
    session_id: str | None = None,
    output_format: dict | None = None,  # 新增
) -> ClaudeAgentOptions:
    # ... 现有逻辑 ...

    return ClaudeAgentOptions(
        model=config.sdk.model,
        output_format=output_format,  # 传递给 SDK
        # ... 其他参数 ...
    )
```

### 3. 修改 API 路由

在 `src/api/routes.py` 中调用时传入 `output_format`：

```python
from src.agent.schema_registry import get_output_format

@app.post("/v1/agent/messages")
async def create_agent_message(...):
    sop = (structured_output_profile or "").strip() or None
    output_fmt = get_output_format(sop)  # 动态获取 Schema

    result = await execute_agent_message(
        config=config,
        prompt=prepared_prompt,
        cwd=working_dir,
        session_id=session_id,
        output_format=output_fmt,  # 传递给 executor
        final_answer_text_policy=text_policy,
    )

    # 此时 result.final_answer 已经是符合 Schema 的 JSON 字符串
    # 可直接 json.loads() 或从 SDK msg["structured_output"] 获取
```

### 4. 修改 `execute_agent_message`

在 `src/agent/executor.py` 中处理 `structured_output`：

```python
async def execute_agent_message(
    *,
    config: AppConfig,
    prompt: str | list[dict[str, Any]],
    cwd: str | Path,
    session_id: str | None = None,
    output_format: dict | None = None,  # 新增
    final_answer_text_policy: str | None = None,
) -> ExecutionResult:
    options = build_agent_options(
        config=config,
        cwd=cwd,
        session_id=session_id,
        output_format=output_format,  # 传递给 SDK
    )

    # ... 现有逻辑 ...

    structured_output = None
    async for message in query(prompt=prompt_input, options=options):
        # ... 现有处理 ...

        if isinstance(message, ResultMessage):
            # SDK 返回的 structured_output（如果配置了 output_format）
            if hasattr(message, "structured_output"):
                structured_output = message.structured_output

    # 返回时附加 structured_output
    return ExecutionResult(
        session_id=resolved_session_id,
        final_answer=final_answer,
        structured_output=structured_output,  # 新增字段
        steps=steps,
        success=success,
        final_answer_text_policy=policy,
    )
```

### 5. 简化后处理（删除冗余代码）

删除或标记为废弃：
- `src/api/jmi_intake_checkout_output.py:92-117` - `strip_markdown_json_fence`, `extract_first_json_value`
- `src/api/routes.py:101-127` - `_apply_structured_output_profile` 中的手动解析

直接使用 SDK 返回的 `structured_output`：

```python
def _build_response(
    result: ExecutionResult,
    sop: str | None,
) -> StructuredAgentResponse | AgentResponse:
    if sop and result.structured_output:
        # SDK 已校验，直接返回
        return StructuredAgentResponse(
            session_id=result.session_id,
            structured_output=result.structured_output,
        )
    # 未启用 structured_output_profile 时的常规响应
    return AgentResponse(
        session_id=result.session_id,
        final_answer=result.final_answer,
        steps=result.steps,
        success=result.success,
    )
```

### 6. 更新 SKILL.md（可选，但建议保留）

在 `.claude/skills/jmi-intake-call-checkout/SKILL.md` 中注明：

```markdown
## 输出契约（机器可读，必须遵守）

**注**：当通过 HTTP API 调用且 `structured_output_profile=jmi_intake_call_checkout` 时，
SDK 会自动强制输出符合 `references/output-schema.md` 的 JSON Schema，无需手动约束。

以下约束作为人类可读文档保留：
- 只输出一个 JSON 对象：从第一个 `{` 到最后一个 `}` 即为完整结果
- 禁止使用 Markdown 代码围栏
- 形状唯一来源：全文必须符合 references/output-schema.md
```

## 迁移路径

### 阶段 1：并行实验（1-2 天）
1. 新建 `src/agent/schema_registry.py`
2. 在测试环境中为一个 Skill（如 `jmi_intake_call_checkout`）启用 `output_format`
3. 对比 SDK Structured Outputs 和当前后处理方案的输出一致性

### 阶段 2：全量迁移（3-5 天）
1. 修改 `build_agent_options`、`execute_agent_message`、`routes.py`
2. 为所有现有 Skill 添加 Schema 映射
3. 删除冗余的后处理代码
4. 更新单元测试

### 阶段 3：清理（1-2 天）
1. 删除 `extract_first_json_value` 等废弃函数
2. 更新文档和 API 说明
3. 性能测试和回归测试

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| SDK `structured_output` 字段位置不确定 | 中 | 查阅 SDK 文档确认 ResultMessage 结构 |
| 旧版 SDK 不支持 `output_format` | 高 | 升级到最新版 `claude-agent-sdk` |
| 现有调用方依赖后处理逻辑 | 中 | 保留 `structured_error` 字段向后兼容 |
| 模型版本不支持 Structured Outputs | 高 | 确保使用 `claude-sonnet-4-5` 或更高版本 |

## 建议

✅ **强烈推荐迁移到 SDK Structured Outputs**

理由：
1. **项目已有完善的 Pydantic 模型**（`JmiIntakeCallCheckoutOutput`、`JmiFreshClaimDocCheckOutput`），迁移成本低
2. **API 设计已支持 `structured_output_profile`**，只需改后端实现，前端无感知
3. **可删除 ~150 行后处理代码**，降低维护成本和 Bug 风险
4. **符合 SDK 设计意图**，利用原生能力而非绕过

建议时间线：**1-2 周完成迁移**，先在测试环境验证一个 Skill，再全量推广。
