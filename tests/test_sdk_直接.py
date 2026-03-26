#!/usr/bin/env python3
"""直接测试 Claude Agent SDK"""
import asyncio
import os
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, query

# 配置环境变量（Claude Code 2.x 主要读取 ANTHROPIC_*）
os.environ["ANTHROPIC_BASE_URL"] = "http://localhost:4000/v1"
os.environ["ANTHROPIC_API_KEY"] = "sk-1234"
# 兼容保留：历史上部分代理会读取 OPENAI_*
os.environ["OPENAI_BASE_URL"] = "http://localhost:4000/v1"
os.environ["OPENAI_API_KEY"] = "sk-1234"


async def test_basic_query():
    """测试基本query"""
    print("测试1: 基本query调用\n" + "="*60)

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5",
        cwd="/tmp",
        max_turns=3,
        permission_mode="acceptEdits",
        allowed_tools=["Read", "Write", "Bash"],
    )

    print(f"Model: {options.model}")
    print(f"CWD: {options.cwd}")
    print(f"Permission: {options.permission_mode}")

    stderr_lines = []
    auth_failed = False
    options.stderr = stderr_lines.append

    try:
        messages = []
        async for message in query(prompt="请说你好", options=options):
            msg_type = type(message).__name__
            print(f"\n收到消息: {msg_type}")
            print(f"内容: {str(message)[:200]}")
            if isinstance(message, AssistantMessage) and message.error == "authentication_failed":
                auth_failed = True
            messages.append(message)

        print(f"\n总共收到 {len(messages)} 条消息")
        return True

    except Exception as e:
        print(f"\n错误: {e}")
        if stderr_lines:
            print("\nCLI stderr（最近20行）:")
            for line in stderr_lines[-20:]:
                print(line)
        if auth_failed:
            print(
                "\n提示: 当前 Claude CLI 处于未登录状态。"
                "请先执行 `claude auth login`，或配置可用的 `ANTHROPIC_API_KEY`。"
            )
        import traceback
        traceback.print_exc()
        return False


async def main():
    success = await test_basic_query()
    if success:
        print("\n✅ SDK测试成功")
    else:
        print("\n❌ SDK测试失败")


if __name__ == "__main__":
    asyncio.run(main())
