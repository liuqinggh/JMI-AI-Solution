from __future__ import annotations

from app.agents.client import _build_sdk_env, _use_managed_provider
from app.core.config import ClaudeSettings, Settings


def test_use_managed_provider_detects_vertex_flag():
    assert _use_managed_provider({"CLAUDE_CODE_USE_VERTEX": "1"}) is True


def test_build_sdk_env_keeps_vertex_env_without_local_proxy_values():
    settings = Settings(
        claude=ClaudeSettings(
            model="claude-sonnet-4-5",
            base_url="http://localhost:4000",
            api_key="sk-local",
            env={
                "CLAUDE_CODE_USE_VERTEX": "1",
                "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/fake-adc.json",
                "ANTHROPIC_VERTEX_PROJECT_ID": "ai-model-487001",
                "CLOUD_ML_REGION": "global",
            },
        )
    )

    env = _build_sdk_env(settings.claude)

    assert env["CLAUDE_CODE_USE_VERTEX"] == "1"
    assert env["ANTHROPIC_VERTEX_PROJECT_ID"] == "ai-model-487001"
    assert "ANTHROPIC_BASE_URL" not in env
    assert "ANTHROPIC_API_KEY" not in env


def test_build_sdk_env_injects_local_proxy_values_when_vertex_disabled():
    settings = Settings(
        claude=ClaudeSettings(
            model="claude-sonnet-4-5",
            base_url="http://localhost:4000",
            api_key="sk-local",
            env={},
        )
    )

    env = _build_sdk_env(settings.claude)

    assert env["ANTHROPIC_BASE_URL"] == "http://localhost:4000"
    assert env["ANTHROPIC_API_KEY"] == "sk-local"
