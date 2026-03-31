from __future__ import annotations

import os
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

from app.config import AppConfig


def _is_truthy_env(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _use_managed_provider(env: dict[str, str]) -> bool:
    keys = (
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_FOUNDRY",
    )
    return any(_is_truthy_env(os.environ.get(key) or env.get(key)) for key in keys)


def build_agent_options(
    config: AppConfig,
    cwd: str | Path,
    session_id: str | None = None,
    output_format: dict | None = None,
) -> ClaudeAgentOptions:
    is_resume = session_id is not None

    if _use_managed_provider(config.sdk.env):
        # 托管 provider 模式下依赖外部环境（如 GCP ADC），避免覆盖为本地代理配置
        env = dict(config.sdk.env)
    else:
        env = {
            "ANTHROPIC_BASE_URL": config.sdk.base_url,
            "ANTHROPIC_API_KEY": config.sdk.api_key,
            "OPENAI_BASE_URL": config.sdk.base_url,
            "OPENAI_API_KEY": config.sdk.api_key,
            **config.sdk.env,
        }

    return ClaudeAgentOptions(
        model=config.sdk.model,
        cwd=str(cwd),
        setting_sources=config.sdk.setting_sources,
        allowed_tools=config.sdk.allowed_tools,
        permission_mode=config.sdk.permission_mode,
        max_turns=config.sdk.max_turns,
        system_prompt=config.agent.system_prompt,
        continue_conversation=is_resume,
        resume=session_id,
        env=env,
        cli_path=config.sdk.cli_path,
        output_format=output_format,
    )
