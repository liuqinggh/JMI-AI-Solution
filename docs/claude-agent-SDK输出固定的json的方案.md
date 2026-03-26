是的，对于**第一种方法（使用 `ClaudeAgentOptions.output_format` 配置 Structured Outputs）**，**不同的 Skill 不需要实现不同的 HTTP 接口**。

你可以只暴露**一个统一的对外接口**（例如 `/agent/run` 或 `/process`），然后在后端代码中**动态选择对应的 JSON Schema**，实现“不同 Skill → 不同结构化输出”的效果。

### 为什么不需要多个接口？

- `output_format` 是**每次调用 `query()` 时**传入的参数（运行时绑定），不是 Skill 本身固有的属性。
- 一个 Skill 可以被同一个 Agent 多次调用，但每次调用时你可以传入**不同的 `output_format`**（不同的 Pydantic Model 或 JSON Schema）。
- 后端根据用户请求的参数（例如 `skill_name` 或 `task_type`）来决定加载哪个 Schema，Claude Agent SDK 会强制最终输出匹配该 Schema，并返回 `structured_output` 字段（已验证的 dict）。
- 这样对外调用方只需调用一个 API，传入不同的 skill 参数，就能得到对应结构的 JSON，非常适合生产服务（REST/gRPC/MCP 等）。

### 推荐实现方式（统一接口 + 动态 Schema 绑定）

**1. 定义每个 Skill 对应的输出 Model（建议建一个 schemas/ 目录）**

```python
# schemas/invoice.py
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class InvoiceOutput(BaseModel):
    file_name: str
    invoice_number: str
    total_amount: float
    items: List[Dict]
    confidence: float
    issues: List[str] = Field(default_factory=list)

# schemas/weekly_report.py
class WeeklyReportOutput(BaseModel):
    period: str
    summary: str
    key_metrics: Dict[str, float]
    action_items: List[str]
    confidence: float
```

**2. 统一 FastAPI 接口（推荐）**

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from claude_agent_sdk import query, ClaudeAgentOptions
from schemas.invoice import InvoiceOutput
from schemas.weekly_report import WeeklyReportOutput
import importlib

app = FastAPI()

class AgentRequest(BaseModel):
    skill_name: str          # e.g. "pdf-invoice-processor" 或 "weekly-report-generator"
    prompt: str
    file_id: str = None      # 可选，如果需要处理文件
    # 其他通用参数...

# Schema 映射表（可扩展到动态从文件加载）
SCHEMA_MAP = {
    "pdf-invoice-processor": InvoiceOutput,
    "weekly-report-generator": WeeklyReportOutput,
    # 添加更多 Skill...
}

@app.post("/agent/run")
async def run_agent(req: AgentRequest):
    schema_model = SCHEMA_MAP.get(req.skill_name)
    if not schema_model:
        raise HTTPException(400, f"Unknown skill: {req.skill_name}")

    # 动态生成 output_format
    output_format = {
        "type": "json_schema",
        "schema": schema_model.model_json_schema()
    }

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5",   # 支持 structured outputs 的模型
        allowed_tools=["Skill", "Read", "Write", "Bash"],
        output_format=output_format,   # ← 关键：动态绑定
        setting_sources=["project"],   # 加载 Skill
    )

    full_prompt = f"""
    请使用 {req.skill_name} Skill 处理任务。
    {req.prompt}
    严格按照指定的 JSON Schema 输出，不要添加任何额外文字。
    """

    try:
        result = None
        async for msg in query(prompt=full_prompt, options=options):
            if msg.get("type") == "result" and "structured_output" in msg:
                result = msg["structured_output"]
                break

        # result 已经是 dict，且符合对应 Skill 的结构
        return {
            "status": "success",
            "skill_name": req.skill_name,
            "structured_output": result
        }
    except Exception as e:
        raise HTTPException(500, str(e))
```

### 优点

- **一个接口搞定所有 Skill**：对外调用方只需传 `skill_name`，后端自动匹配 Schema。
- **类型安全**：每个 Skill 有自己的 Pydantic Model，后续系统可直接用对应 Model 解析。
- **易扩展**：新增 Skill 时，只需加一个 Pydantic Model + 映射表，不用改接口。
- **与 SKILL.md 结合**：在每个 Skill 的 `SKILL.md` 中仍写清楚“本 Skill 期望输出 XXX 结构”，作为提示强化（即使有 structured outputs，也建议保留）。

### 其他可选架构（如果需要更解耦）

- **按 Skill 拆分 endpoint**（`/agent/invoice`、`/agent/weekly-report`）：每个 endpoint 硬编码自己的 Schema，代码更简单，但接口数量会增多。
- **使用 MCP Server**：把整个 Agent 包装成标准化工具，外部直接调用时传入 skill 参数 + schema 描述。
- **动态加载 Schema**：把所有 Schema 存成 JSON 文件或数据库，根据 skill_name 运行时读取。

**总结回答你的问题**：
不需要为不同 Skill 实现不同接口。第一种方法（structured outputs）天然支持在**同一个调用点动态切换 Schema**，一个统一接口即可完美支持多个 Skill 的不同 JSON 输出结构。

如果你想，我可以给你：

- 完整可运行的 FastAPI 项目模板（包含多个 Schema 示例）
- 如何把 Schema 也放到 Skill 文件夹里实现更自动化的绑定
- 处理文件 + structured output 的完整端到端示例

告诉我你当前有多少个 Skill，或者具体业务场景（发票、周报、合同等），我可以帮你细化代码！
