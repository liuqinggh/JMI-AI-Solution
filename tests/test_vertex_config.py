#!/usr/bin/env python3
"""测试 Vertex AI 配置的脚本"""

import os
import asyncio
from pathlib import Path

from src.config import get_config, configure_sdk_environment
from src.agent.executor import execute_agent_message


async def test_vertex_config():
    """测试 Vertex AI 配置"""
    print("=== 测试 Vertex AI 配置 ===\n")

    # 加载配置
    config = get_config()
    print(f"📋 配置文件加载成功")
    print(f"   Model: {config.sdk.model}")
    print(f"   Max Turns: {config.sdk.max_turns}")

    # 检查环境变量
    print(f"\n🔍 检查环境变量:")
    env_vars = config.sdk.env
    for key, value in env_vars.items():
        display_value = value if key != "GOOGLE_APPLICATION_CREDENTIALS" else f"{value[:50]}..."
        print(f"   {key}: {display_value}")

    # 验证 Vertex AI 模式
    use_vertex = env_vars.get("CLAUDE_CODE_USE_VERTEX") == "1"
    print(f"\n✅ Vertex AI 模式: {'已启用' if use_vertex else '未启用'}")

    if use_vertex:
        creds_path = env_vars.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path and Path(creds_path).exists():
            print(f"✅ 凭证文件存在: {creds_path}")
        else:
            print(f"❌ 凭证文件不存在: {creds_path}")
            return

    # 配置 SDK 环境
    configure_sdk_environment(config)
    print(f"\n🔧 SDK 环境已配置")

    # 测试简单对话
    print(f"\n🧪 测试简单对话...")
    try:
        result = await execute_agent_message(
            config=config,
            prompt="你好，请用一句话介绍你自己。",
            cwd=Path.cwd(),
        )
        print(f"✅ 对话测试成功!")
        print(f"   Session ID: {result.session_id}")
        print(f"   Success: {result.success}")
        print(f"   回复: {result.final_answer[:100]}...")
    except Exception as e:
        print(f"❌ 对话测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_vertex_config())
