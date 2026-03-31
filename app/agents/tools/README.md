# Agent Tools

此目录包含自定义的 MCP (Model Context Protocol) 工具，供 Claude Agent SDK 使用。

## 工具优先级

根据 `.claude/rules/claude_agent_sdk.md` 规则：

1. **MCP Servers（首选）** - 注册 Python 函数作为工具，支持复杂逻辑
2. **内置工具** - Read/Write/Edit/Bash 等，通过 `allowed_tools` 严格限制
3. **自定义工具** - 必须提供清晰描述、输入示例和输出格式

## 创建新工具

### 1. 定义工具函数

```python
# app/agents/tools/my_tool.py
async def my_custom_tool(param1: str, param2: int = 10) -> dict:
    """工具描述（至少 3-4 句）
    
    使用场景：
    - 何时使用此工具
    - 适合什么样的查询
    - 有什么限制
    
    输入示例：
    - param1: "example input"
    - param2: 5
    
    输出示例：
    {
        "result": "...",
        "metadata": {...}
    }
    """
    # 实现工具逻辑
    return {"result": "..."}

# MCP Tool 元数据
TOOL_METADATA = {
    "name": "my_custom_tool",
    "description": "详细描述工具功能、使用场景、输入输出格式",
    "parameters": {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "参数1的说明",
            },
            "param2": {
                "type": "integer",
                "description": "参数2的说明（可选）",
                "default": 10,
            },
        },
        "required": ["param1"],
    },
}
```

### 2. 注册到 __init__.py

```python
# app/agents/tools/__init__.py
from app.agents.tools.my_tool import my_custom_tool

__all__ = [
    "example_search_tool",
    "my_custom_tool",  # 添加新工具
]
```

### 3. 在配置中启用工具

```yaml
# conf/config.yaml
sdk:
  allowed_tools:
    - Read
    - Write
    - Edit
    - my_custom_tool  # 添加到允许列表
```

## 安全规范

根据 `.claude/rules/code_style_and_security.md`：

1. **输入验证** - 所有工具必须验证输入参数
2. **沙箱隔离** - 危险操作（文件写入、命令执行）必须 sandbox
3. **权限控制** - 使用 `can_use_tool` hook 控制工具访问
4. **敏感数据** - 日志中脱敏 API Key、密码等
5. **错误处理** - 提供清晰的错误信息，不暴露内部细节

## 示例工具

查看 `example_tool.py` 了解完整的工具实现示例。

## 测试工具

```python
# tests/test_my_tool.py
import pytest
from app.agents.tools.my_tool import my_custom_tool

@pytest.mark.asyncio
async def test_my_custom_tool():
    result = await my_custom_tool(param1="test", param2=5)
    assert result["result"] is not None
```

## 参考文档

- [Claude Agent SDK 文档](https://github.com/anthropics/claude-agent-sdk)
- [MCP 协议规范](https://modelcontextprotocol.io/)
- 项目规则：`.claude/rules/claude_agent_sdk.md`
