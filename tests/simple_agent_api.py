#!/usr/bin/env python3
"""
最小 HTTP 客户端：访问本服务的 POST /v1/agent/messages。

依赖：httpx（uv dev 已含）。服务需已启动（默认 http://127.0.0.1:8000）。

示例：
  uv run python scripts/simple_agent_api.py
  uv run python scripts/simple_agent_api.py "总结一下本对话规则"
  uv run python scripts/simple_agent_api.py "阅读附件" -f ~/Downloads/report.pdf
  AGENT_API_BASE_URL=http://127.0.0.1:8001 uv run python scripts/simple_agent_api.py "ping"

多轮（第二轮起带上首轮返回的 session_id）：
  uv run python scripts/simple_agent_api.py "记住数字 7"
  uv run python scripts/simple_agent_api.py "刚才的数字是？" --session <上轮 session_id>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

DEFAULT_BASE = os.environ.get("AGENT_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _mime_for_path(path: Path) -> str:
    s = path.suffix.lower()
    mapping = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".md": "text/markdown",
        ".txt": "text/plain",
    }
    return mapping.get(s, "application/octet-stream")


def main() -> int:
    parser = argparse.ArgumentParser(description="调用 agent-sdk-api-service /v1/agent/messages")
    parser.add_argument("prompt", nargs="?", default="你好，用一句话介绍你能做什么。")
    parser.add_argument("-b", "--base", default=DEFAULT_BASE, help="API 根地址，默认读 AGENT_API_BASE_URL")
    parser.add_argument(
        "-f",
        "--file",
        action="append",
        default=[],
        metavar="PATH",
        help="上传文件，可重复指定多次",
    )
    parser.add_argument("--session", metavar="ID", help="延续多轮对话")
    parser.add_argument(
        "--structured-profile",
        metavar="NAME",
        help="structured_output_profile，如 jmi_intake_call_checkout、jmi_fresh_claim_doc_check（此时服务端默认仅保留最后一轮助手文本）",
    )
    parser.add_argument(
        "--final-answer-policy",
        choices=("full", "last_assistant_turn"),
        metavar="POLICY",
        help="覆盖 final_answer_text_policy：full 拼接多轮，last_assistant_turn 仅最后一轮",
    )
    parser.add_argument("-t", "--timeout", type=float, default=600.0)
    parser.add_argument("-q", "--quiet", action="store_true", help="只打印 final_answer")
    args = parser.parse_args()

    url = f"{args.base}/v1/agent/messages"
    mp: list[tuple[str, tuple[str | None, bytes | str] | tuple[str, bytes, str]]] = [
        ("prompt", (None, args.prompt)),
    ]
    if args.session:
        mp.append(("session_id", (None, args.session)))
    if args.structured_profile:
        mp.append(("structured_output_profile", (None, args.structured_profile)))
    if args.final_answer_policy:
        mp.append(("final_answer_text_policy", (None, args.final_answer_policy)))

    for raw in args.file:
        path = Path(raw).expanduser()
        if not path.is_file():
            print(f"错误: 不是文件 — {path}", file=sys.stderr)
            return 2
        mime = _mime_for_path(path)
        mp.append(("files", (path.name, path.read_bytes(), mime)))

    try:
        with httpx.Client(timeout=args.timeout) as client:
            r = client.post(url, files=mp)
    except httpx.ConnectError as e:
        print(f"无法连接 {url}（请先启动服务）: {e}", file=sys.stderr)
        return 3

    try:
        body = r.json()
    except Exception:
        print(r.text[:2000], file=sys.stderr)
        return 4 if r.is_error else 0

    if args.quiet and isinstance(body.get("final_answer"), str):
        print(body["final_answer"])
        return 0 if r.is_success else 1

    out = {
        "status_code": r.status_code,
        "body": body,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if r.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
