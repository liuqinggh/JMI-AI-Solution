#!/usr/bin/env python3
"""
API 接口手动测试脚本（需本机已启动服务）。
测试: 1. 单轮对话  2. 多轮对话  3. 文件上传识别

用法: 在项目根目录执行  uv run python tests/test_api.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"

# 测试 3 / 4 使用的本地图片（不存在则自动跳过，不计入失败）
IMAGE_UPLOAD_TEST = Path(
    "/Users/cd-la-067/Downloads/Gemini_Generated_Image_4lw8iw4lw8iw4lw8.png"
)
IMAGE_MULTITURN_TEST = Path(
    "/Users/cd-la-067/Downloads/Gemini_Generated_Image_c2ubfwc2ubfwc2ub.png"
)


def _preview(text: str | None, n: int = 200) -> str:
    if text is None:
        return "(无 final_answer)"
    text = text.strip()
    if not text:
        return "(空字符串)"
    return text[:n] + ("..." if len(text) > n else "")


def print_agent_response(response: httpx.Response, *, answer_preview_len: int = 200) -> dict | None:
    """打印响应；非 2xx 或缺少字段时不抛错，返回 None。"""
    print(f"状态码: {response.status_code}")
    try:
        result = response.json()
    except Exception:
        print(f"响应非 JSON，正文前 500 字:\n{response.text[:500]}")
        return None

    if response.is_error:
        detail = result.get("detail", result)
        print(f"错误详情: {detail}")
        return None

    final_answer = result.get("final_answer")
    print(f"Session ID: {result.get('session_id')}")
    print(f"成功: {result.get('success')}")
    print(f"回答: {_preview(final_answer, answer_preview_len)}")
    print(f"步骤数: {len(result.get('steps', []))}")
    return result


async def run_single_turn() -> dict | None:
    """测试1: 单轮对话（手动脚本用，勿以 test_ 命名以免被 pytest 收集）。"""
    print("\n" + "=" * 60)
    print("测试1: 单轮对话")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{BASE_URL}/v1/agent/messages",
            files={"prompt": (None, "你好，请介绍一下你自己")},
        )

        return print_agent_response(response)


async def run_multi_turn() -> dict | None:
    """测试2: 多轮对话"""
    print("\n" + "=" * 60)
    print("测试2: 多轮对话")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        print("\n[第1轮] 创建会话...")
        resp1 = await client.post(
            f"{BASE_URL}/v1/agent/messages",
            files={"prompt": (None, "我有一个数字: 42")},
        )
        result1 = print_agent_response(resp1, answer_preview_len=150)
        if not result1:
            return None
        session_id = result1.get("session_id")
        if not session_id:
            print("错误: 首轮未返回 session_id，跳过后续轮次")
            return None

        print("\n[第2轮] 延续会话...")
        resp2 = await client.post(
            f"{BASE_URL}/v1/agent/messages",
            files={
                "prompt": (None, "这个数字加10等于多少？"),
                "session_id": (None, session_id),
            },
        )
        result2 = print_agent_response(resp2, answer_preview_len=150)
        if not result2:
            return None

        print("\n[第3轮] 测试上下文记忆...")
        resp3 = await client.post(
            f"{BASE_URL}/v1/agent/messages",
            files={
                "prompt": (None, "我最开始说的数字是多少？"),
                "session_id": (None, session_id),
            },
        )
        return print_agent_response(resp3, answer_preview_len=150)


async def run_file_upload() -> dict | None:
    """测试3: 文件上传和图片识别"""
    print("\n" + "=" * 60)
    print("测试3: 文件上传和图片识别")
    print("=" * 60)

    image_path = IMAGE_UPLOAD_TEST

    if not image_path.exists():
        print(f"跳过: 图片不存在 {image_path}")
        return None

    async with httpx.AsyncClient(timeout=120.0) as client:
        with open(str(image_path), "rb") as f:
            files = {"files": ("diagram.png", f, "image/png")}
            data = {"prompt": "这张图片展示了什么内容？请详细描述"}

            response = await client.post(
                f"{BASE_URL}/v1/agent/messages",
                files=files,
                data=data,
            )

        return print_agent_response(response, answer_preview_len=500)


async def run_multi_turn_with_file() -> dict | None:
    """测试4: 多轮对话 + 文件上传"""
    print("\n" + "=" * 60)
    print("测试4: 多轮对话中上传文件")
    print("=" * 60)

    image_path = IMAGE_MULTITURN_TEST

    if not image_path.exists():
        print(f"跳过: 图片不存在 {image_path}")
        return None

    async with httpx.AsyncClient(timeout=120.0) as client:
        print("\n[第1轮] 上传图片...")
        with open(str(image_path), "rb") as f:
            files = {"files": ("architecture.png", f, "image/png")}
            data = {"prompt": "请识别这张架构图"}

            resp1 = await client.post(
                f"{BASE_URL}/v1/agent/messages",
                files=files,
                data=data,
            )

        result1 = print_agent_response(resp1, answer_preview_len=200)
        if not result1:
            return None
        session_id = result1.get("session_id")
        if not session_id:
            print("错误: 首轮未返回 session_id，跳过第2轮")
            return None

        print("\n[第2轮] 基于图片内容提问（multipart，无新文件）...")
        resp2 = await client.post(
            f"{BASE_URL}/v1/agent/messages",
            files={
                "prompt": (None, "这个架构有几层？"),
                "session_id": (None, session_id),
            },
        )
        return print_agent_response(resp2, answer_preview_len=200)


async def main() -> None:
    print("\n🧪 开始 API 接口测试...")
    print(f"目标服务: {BASE_URL}")
    print("提示: 请在项目根目录运行，且已启动 uvicorn（需可读 conf/config.yaml）。")

    failed: list[str] = []

    if await run_single_turn() is None:
        failed.append("单轮对话")

    if await run_multi_turn() is None:
        failed.append("多轮对话")

    r3 = await run_file_upload()
    if r3 is None and IMAGE_UPLOAD_TEST.exists():
        failed.append("文件上传")

    r4 = await run_multi_turn_with_file()
    if r4 is None and IMAGE_MULTITURN_TEST.exists():
        failed.append("多轮+文件")

    print("\n" + "=" * 60)
    if failed:
        print(f"⚠️ 未通过: {', '.join(failed)}（见上方状态码与 detail）")
        sys.exit(1)
    print("✅ 已执行的测试均返回 2xx 且结构正常")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
