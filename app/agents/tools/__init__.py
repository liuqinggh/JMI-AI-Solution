"""Custom tools for Claude Agent SDK.

This module contains MCP (Model Context Protocol) compatible tools
that can be registered with the Claude Agent SDK.

优先使用 MCP Servers 实现自定义工具，确保：
1. 工具描述清晰（至少 3-4 句说明）
2. 输入输出示例完整
3. 权限控制严格（避免危险操作）
"""

from app.agents.tools.example_tool import example_search_tool

__all__ = [
    "example_search_tool",
]
