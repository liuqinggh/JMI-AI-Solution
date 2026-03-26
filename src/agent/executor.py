from __future__ import annotations

import logging
from collections.abc import AsyncIterable, AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    TaskStartedMessage,
    TextBlock,
    query,
)

from src.agent.options import build_agent_options
from src.api.models import ExecutionResult
from src.config import AppConfig
from src.tracing.langfuse_tracer import LangfuseTracer

logger = logging.getLogger(__name__)

# Global tracer instance (will be initialized by routes)
_tracer: LangfuseTracer | None = None


def set_tracer(tracer: LangfuseTracer) -> None:
    """Set global tracer instance."""
    global _tracer
    _tracer = tracer


def get_tracer() -> LangfuseTracer | None:
    """Get global tracer instance."""
    return _tracer

_CLI_EXIT_CODE_MARKER = "Command failed with exit code"


def _looks_like_cli_exit_error(exc: BaseException) -> bool:
    return _CLI_EXIT_CODE_MARKER in str(exc)


def assemble_final_answer(
    *,
    assistant_turn_texts: list[str],
    result_fallback: str | None,
    policy: str,
) -> str:
    """
    assistant_turn_texts: 每一轮 AssistantMessage 的可展示文本（该轮内多个 TextBlock 已用换行拼接）。
    result_fallback: 与历史逻辑一致——仅当整次对话从未产生助手文本时，采用 ResultMessage.result。
    policy: full 拼接所有轮次；last_assistant_turn 仅最后一轮。
    """
    if assistant_turn_texts:
        if policy == "last_assistant_turn":
            body = assistant_turn_texts[-1]
        else:
            body = "\n".join(assistant_turn_texts)
    else:
        body = (result_fallback or "").strip()
    return body if body else "任务已执行完成"


async def execute_agent_message(
    *,
    config: AppConfig,
    prompt: str | list[dict[str, Any]],
    cwd: str | Path,
    session_id: str | None = None,
    output_format: dict | None = None,
    final_answer_text_policy: str | None = None,
    user_id: str | None = None,
) -> ExecutionResult:
    start_time = datetime.now()
    tracer = get_tracer()

    options = build_agent_options(
        config=config,
        cwd=cwd,
        session_id=session_id,
        output_format=output_format,
    )
    stderr_lines: list[str] = []
    options.stderr = stderr_lines.append

    policy = (final_answer_text_policy or config.api.final_answer_text_policy).strip()
    if policy not in ("full", "last_assistant_turn"):
        policy = "full"

    steps: list[dict[str, str]] = []
    assistant_turn_texts: list[str] = []
    result_fallback: str | None = None
    resolved_session_id = session_id
    success = True
    got_result = False
    structured_output: dict[str, Any] | None = None
    prompt_input: str | AsyncIterable[dict[str, Any]]

    if isinstance(prompt, str):
        prompt_input = prompt
    else:
        prompt_input = _build_user_message_stream(prompt, session_id)

    # Prepare metadata for tracing
    metadata = {
        "cwd": str(cwd),
        "model": config.sdk.model,
        "max_turns": config.sdk.max_turns,
        "output_format_enabled": output_format is not None,
        "final_answer_policy": policy,
    }

    try:
        async for message in query(prompt=prompt_input, options=options):
            maybe_session_id = getattr(message, "session_id", None)
            if maybe_session_id and not resolved_session_id:
                resolved_session_id = maybe_session_id

            if config.api.return_steps:
                steps.append(
                    {
                        "type": type(message).__name__,
                        "content": str(message)[: config.api.max_step_preview_chars],
                    }
                )

            if isinstance(message, AssistantMessage):
                line_parts: list[str] = []
                for block in message.content:
                    if isinstance(block, TextBlock):
                        line_parts.append(block.text)
                chunk = "\n".join(p.strip() for p in line_parts if p.strip())
                if chunk:
                    assistant_turn_texts.append(chunk)
            elif isinstance(message, TaskStartedMessage) and not resolved_session_id:
                resolved_session_id = message.session_id
            elif isinstance(message, ResultMessage):
                resolved_session_id = message.session_id or resolved_session_id
                success = not message.is_error
                got_result = True
                if not assistant_turn_texts and message.result:
                    result_fallback = message.result.strip() or None
                # 提取 SDK 返回的 structured_output（如果启用了 output_format）
                if hasattr(message, "structured_output"):
                    structured_output = message.structured_output
    except Exception as exc:
        if got_result and _looks_like_cli_exit_error(exc):
            logger.warning("CLI 非零退出码，但已收到 ResultMessage，忽略: %s", exc)
        else:
            raise

    if not resolved_session_id:
        raise RuntimeError("SDK did not return a session_id")

    final_answer = assemble_final_answer(
        assistant_turn_texts=assistant_turn_texts,
        result_fallback=result_fallback,
        policy=policy,
    )

    return ExecutionResult(
        session_id=resolved_session_id,
        final_answer=final_answer,
        steps=steps,
        success=success,
        final_answer_text_policy=policy,
        structured_output=structured_output,
    )


async def _build_user_message_stream(
    content: list[dict[str, Any]],
    session_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    yield {
        "type": "user",
        "session_id": session_id or "",
        "message": {
            "role": "user",
            "content": content,
        },
        "parent_tool_use_id": None,
    }
