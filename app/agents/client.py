from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TaskStartedMessage,
    TextBlock,
    query,
)

from app.core.config import Settings
from app.models.session import PermissionProfile

MANAGED_PROVIDER_ENV_KEYS = (
    "GOOGLE_APPLICATION_CREDENTIALS",
    "ANTHROPIC_VERTEX_PROJECT_ID",
    "CLOUD_ML_REGION",
    "GOOGLE_CLOUD_PROJECT",
)


def _is_truthy_env(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _use_managed_provider(env: dict[str, str]) -> bool:
    keys = (
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_FOUNDRY",
    )
    return any(_is_truthy_env(env.get(key)) for key in keys)


def _build_sdk_env(settings: Settings | Any) -> dict[str, str]:
    claude_settings = getattr(settings, "claude", settings)
    env = dict(claude_settings.env)
    if _use_managed_provider(env):
        for key in MANAGED_PROVIDER_ENV_KEYS:
            if key not in env and os.getenv(key):
                env[key] = os.environ[key]
        return env

    if claude_settings.base_url:
        env["ANTHROPIC_BASE_URL"] = claude_settings.base_url
        env["OPENAI_BASE_URL"] = claude_settings.base_url
    if claude_settings.api_key:
        env["ANTHROPIC_API_KEY"] = claude_settings.api_key
        env["OPENAI_API_KEY"] = claude_settings.api_key
    return env


async def stream_chat(
    *,
    settings: Settings,
    message: str,
    skill_prompt: str,
    cwd: str | Path,
    permission: PermissionProfile,
    resume_session_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    options = ClaudeAgentOptions(
        model=settings.claude.model,
        cwd=str(cwd),
        allowed_tools=permission.allowed_tools,
        permission_mode=permission.permission_mode,
        max_turns=settings.claude.max_turns,
        setting_sources=settings.claude.setting_sources,
        continue_conversation=resume_session_id is not None,
        resume=resume_session_id,
        system_prompt=skill_prompt,
        env=_build_sdk_env(settings),
        cli_path=settings.claude.cli_path,
    )

    emitted_session_started = False
    assistant_chunks: list[str] = []

    async for sdk_message in query(prompt=message, options=options):
        sdk_session_id = getattr(sdk_message, "session_id", None)
        if sdk_session_id and not emitted_session_started:
            emitted_session_started = True
            yield {"event": "session_started", "sdk_session_id": sdk_session_id}

        if isinstance(sdk_message, TaskStartedMessage):
            if sdk_message.session_id and not emitted_session_started:
                emitted_session_started = True
                yield {"event": "session_started", "sdk_session_id": sdk_message.session_id}
            continue

        if isinstance(sdk_message, AssistantMessage):
            text_parts = [block.text for block in sdk_message.content if isinstance(block, TextBlock)]
            chunk = "\n".join(part.strip() for part in text_parts if part.strip())
            if chunk:
                assistant_chunks.append(chunk)
                yield {"event": "assistant_delta", "text": chunk}
            continue

        if isinstance(sdk_message, ResultMessage):
            final_answer = "\n".join(assistant_chunks).strip() or (sdk_message.result or "").strip()
            yield {
                "event": "final",
                "final_answer": final_answer or "任务已执行完成",
                "sdk_session_id": sdk_session_id or resume_session_id,
            }
            continue

        yield {
            "event": "tool_event",
            "message_type": type(sdk_message).__name__,
            "sdk_session_id": sdk_session_id or resume_session_id,
        }
