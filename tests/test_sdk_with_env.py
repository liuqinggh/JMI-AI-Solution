#!/usr/bin/env python3
"""测试带环境变量的 Claude Agent SDK"""
import asyncio
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, query


async def test_with_env():
    """使用env参数测试SDK"""
    print("测试: 使用env参数配置SDK\n" + "="*60)

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5",
        cwd="/tmp",
        max_turns=3,
        permission_mode="acceptEdits",
        allowed_tools=["Read", "Write", "Bash"],
        env={
            "ANTHROPIC_BASE_URL": "http://localhost:4000/v1",
            "ANTHROPIC_API_KEY": "sk-1234",
            "OPENAI_BASE_URL": "http://localhost:4000/v1",
            "OPENAI_API_KEY": "sk-1234",
        }
    )

    print(f"Model: {options.model}")
    print(f"Env: {options.env}")

    stderr_lines = []
    auth_failed = False
    options.stderr = stderr_lines.append

    try:
        messages = []
        async for message in query(prompt="你好，请回复一句话", options=options):
            msg_type = type(message).__name__
            print(f"\n收到: {msg_type}")
            if hasattr(message, 'content'):
                print(f"内容: {message.content}")
            if isinstance(message, AssistantMessage) and message.error == "authentication_failed":
                auth_failed = True
            messages.append(message)

        print(f"\n✅ 成功！收到 {len(messages)} 条消息")
        return True

    except Exception as e:
        print(f"\n❌ 错误: {e}")
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


if __name__ == "__main__":
    asyncio.run(test_with_env())
