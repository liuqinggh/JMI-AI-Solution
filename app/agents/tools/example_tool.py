"""Example MCP tool implementation.

This is a template showing how to create custom tools for Claude Agent SDK.
Replace this with your actual tools (e.g., database queries, API calls, etc.).
"""

from __future__ import annotations

from typing import Any


async def example_search_tool(
    query: str,
    max_results: int = 10,
) -> dict[str, Any]:
    """Example search tool for demonstration purposes.

    This tool demonstrates how to implement a custom MCP tool.
    In production, replace this with actual search logic
    (e.g., database queries, Elasticsearch, vector search, etc.).

    使用场景：
    - 当需要搜索内部知识库时调用此工具
    - 适合查询结构化数据或文档
    - 支持限制返回结果数量

    输入示例：
    - query: "车险理赔流程"
    - max_results: 5

    输出示例：
    {
        "results": [
            {"title": "理赔流程指南", "content": "...", "score": 0.95},
            {"title": "常见问题", "content": "...", "score": 0.87}
        ],
        "total": 2
    }

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 10)

    Returns:
        Dictionary containing search results and metadata

    Raises:
        ValueError: If query is empty or max_results is invalid
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    if max_results < 1 or max_results > 100:
        raise ValueError("max_results must be between 1 and 100")

    # TODO: Replace with actual search implementation
    # Example: query vector database, search API, etc.
    mock_results = [
        {
            "title": f"Result {i+1} for '{query}'",
            "content": f"This is a mock result for demonstration. Query: {query}",
            "score": 0.9 - (i * 0.1),
            "metadata": {
                "source": "example_db",
                "timestamp": "2024-03-26T10:00:00Z",
            },
        }
        for i in range(min(3, max_results))
    ]

    return {
        "results": mock_results,
        "total": len(mock_results),
        "query": query,
        "max_results": max_results,
    }


# MCP Tool registration metadata
# This metadata helps the Agent SDK understand how to use the tool
TOOL_METADATA = {
    "name": "example_search",
    "description": (
        "Search internal knowledge base or documents. "
        "Use this when you need to find specific information from stored data. "
        "The tool returns ranked results with relevance scores. "
        "Best for structured queries about specific topics."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query (required, non-empty string)",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (1-100, default: 10)",
                "default": 10,
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["query"],
    },
}
