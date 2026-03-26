"""测试 SDK Structured Outputs 集成。

验证从 Pydantic Schema → output_format → SDK → structured_output 的完整流程。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.agent.options import build_agent_options
from src.agent.schema_registry import SCHEMA_MAP, get_output_format
from src.api.jmi_intake_checkout_output import JmiIntakeCallCheckoutOutput


def test_get_output_format_returns_none_for_empty_profile():
    """未传 profile 时返回 None。"""
    result = get_output_format(None)
    assert result is None

    result = get_output_format("")
    assert result is None


def test_get_output_format_returns_none_for_unknown_profile():
    """未知 profile 时返回 None。"""
    result = get_output_format("unknown_skill")
    assert result is None


def test_get_output_format_returns_json_schema_for_jmi_intake():
    """jmi_intake_call_checkout profile 返回正确的 output_format。"""
    result = get_output_format("jmi_intake_call_checkout")

    assert result is not None
    assert result["type"] == "json_schema"
    assert "schema" in result
    assert isinstance(result["schema"], dict)

    # 验证 schema 包含必要的字段
    schema = result["schema"]
    assert "properties" in schema
    assert "checklist" in schema["properties"]
    assert "items" in schema["properties"]


def test_get_output_format_returns_json_schema_for_jmi_fresh_claim():
    """jmi_fresh_claim_doc_check profile 返回正确的 output_format。"""
    result = get_output_format("jmi_fresh_claim_doc_check")

    assert result is not None
    assert result["type"] == "json_schema"
    assert "schema" in result
    assert isinstance(result["schema"], dict)

    schema = result["schema"]
    assert "properties" in schema
    assert "documents" in schema["properties"]


def test_schema_map_contains_expected_profiles():
    """SCHEMA_MAP 包含所有支持的 profile。"""
    assert "jmi_intake_call_checkout" in SCHEMA_MAP
    assert "jmi_fresh_claim_doc_check" in SCHEMA_MAP

    # 验证映射的是 Pydantic Model
    assert SCHEMA_MAP["jmi_intake_call_checkout"] is JmiIntakeCallCheckoutOutput


def test_build_agent_options_accepts_output_format(tmp_path):
    """build_agent_options 接受 output_format 参数。"""
    from src.config import AppConfig, SdkSettings, AgentSettings, ApiSettings, StorageSettings

    config = AppConfig(
        sdk=SdkSettings(
            model="claude-sonnet-4-5",
            base_url="http://localhost:8080",
            api_key="test-key",
        ),
        agent=AgentSettings(),
        api=ApiSettings(),
        storage=StorageSettings(),
    )

    output_format = {
        "type": "json_schema",
        "schema": {"type": "object"}
    }

    options = build_agent_options(
        config=config,
        cwd=tmp_path,
        output_format=output_format,
    )

    # 验证 output_format 被传递到 ClaudeAgentOptions
    assert options.output_format == output_format


def test_build_agent_options_output_format_is_optional(tmp_path):
    """build_agent_options 的 output_format 参数是可选的（向后兼容）。"""
    from src.config import AppConfig, SdkSettings, AgentSettings, ApiSettings, StorageSettings

    config = AppConfig(
        sdk=SdkSettings(
            model="claude-sonnet-4-5",
            base_url="http://localhost:8080",
            api_key="test-key",
        ),
        agent=AgentSettings(),
        api=ApiSettings(),
        storage=StorageSettings(),
    )

    # 不传 output_format 参数
    options = build_agent_options(config=config, cwd=tmp_path)

    # 应该没有设置 output_format（或为 None）
    assert not hasattr(options, 'output_format') or options.output_format is None


@pytest.mark.asyncio
async def test_execute_agent_message_accepts_output_format(tmp_path, monkeypatch):
    """execute_agent_message 接受 output_format 并传递给 SDK。"""
    from src.agent.executor import execute_agent_message
    from src.config import AppConfig, SdkSettings, AgentSettings, ApiSettings, StorageSettings

    config = AppConfig(
        sdk=SdkSettings(
            model="claude-sonnet-4-5",
            base_url="http://localhost:8080",
            api_key="test-key",
        ),
        agent=AgentSettings(),
        api=ApiSettings(),
        storage=StorageSettings(),
    )

    output_format = {
        "type": "json_schema",
        "schema": {"type": "object"}
    }

    # Mock SDK query 函数
    call_args_captured = {}

    async def mock_query(prompt: Any, options: Any):
        call_args_captured["options"] = options
        # 使用简单的 Mock 对象而非真实 SDK 消息类
        class MockMessage:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class MockTextBlock:
            def __init__(self, text):
                self.text = text

        # TaskStartedMessage
        yield MockMessage(session_id="test-session", type="task_started")

        # AssistantMessage
        yield MockMessage(
            session_id="test-session",
            content=[MockTextBlock('{"test": "ok"}')],
            type="assistant"
        )

        # ResultMessage
        yield MockMessage(
            session_id="test-session",
            is_error=False,
            result="Task completed",
            type="result"
        )

    # Patch isinstance checks
    from claude_agent_sdk import AssistantMessage, ResultMessage, TaskStartedMessage, TextBlock

    original_isinstance = isinstance
    def custom_isinstance(obj, classinfo):
        if hasattr(obj, 'type'):
            if classinfo is TaskStartedMessage and obj.type == "task_started":
                return True
            if classinfo is AssistantMessage and obj.type == "assistant":
                return True
            if classinfo is ResultMessage and obj.type == "result":
                return True
            if classinfo is TextBlock and hasattr(obj, 'text'):
                return True
        return original_isinstance(obj, classinfo)

    monkeypatch.setattr("builtins.isinstance", custom_isinstance)
    monkeypatch.setattr("src.agent.executor.query", mock_query)

    result = await execute_agent_message(
        config=config,
        prompt="test",
        cwd=tmp_path,
        output_format=output_format,
    )

    # 验证 output_format 被传递给 SDK
    assert call_args_captured["options"].output_format == output_format


@pytest.mark.asyncio
async def test_execute_agent_message_extracts_structured_output_from_result_message(tmp_path, monkeypatch):
    """execute_agent_message 从 ResultMessage 提取 structured_output。"""
    from src.agent.executor import execute_agent_message
    from src.config import AppConfig, SdkSettings, AgentSettings, ApiSettings, StorageSettings

    config = AppConfig(
        sdk=SdkSettings(
            model="claude-sonnet-4-5",
            base_url="http://localhost:8080",
            api_key="test-key",
        ),
        agent=AgentSettings(),
        api=ApiSettings(),
        storage=StorageSettings(),
    )

    expected_structured_output = {
        "checklist": "intake_call_checkout",
        "items": [{"id": 1, "name": "test"}]
    }

    # Mock SDK query 返回带 structured_output 的 ResultMessage
    async def mock_query(prompt: Any, options: Any):
        class MockMessage:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        yield MockMessage(session_id="test-session", type="task_started")

        # 模拟 SDK 返回 structured_output
        yield MockMessage(
            session_id="test-session",
            is_error=False,
            result="Completed",
            structured_output=expected_structured_output,
            type="result"
        )

    # Patch isinstance checks
    from claude_agent_sdk import AssistantMessage, ResultMessage, TaskStartedMessage

    original_isinstance = isinstance
    def custom_isinstance(obj, classinfo):
        if hasattr(obj, 'type'):
            if classinfo is TaskStartedMessage and obj.type == "task_started":
                return True
            if classinfo is AssistantMessage and obj.type == "assistant":
                return True
            if classinfo is ResultMessage and obj.type == "result":
                return True
        return original_isinstance(obj, classinfo)

    monkeypatch.setattr("builtins.isinstance", custom_isinstance)
    monkeypatch.setattr("src.agent.executor.query", mock_query)

    result = await execute_agent_message(
        config=config,
        prompt="test",
        cwd=tmp_path,
        output_format={"type": "json_schema", "schema": {}},
    )

    # 验证 structured_output 被提取
    assert result.structured_output == expected_structured_output


@pytest.mark.asyncio
async def test_execute_agent_message_structured_output_is_optional(tmp_path, monkeypatch):
    """execute_agent_message 在未启用 structured_output 时返回 None。"""
    from src.agent.executor import execute_agent_message
    from src.config import AppConfig, SdkSettings, AgentSettings, ApiSettings, StorageSettings

    config = AppConfig(
        sdk=SdkSettings(
            model="claude-sonnet-4-5",
            base_url="http://localhost:8080",
            api_key="test-key",
        ),
        agent=AgentSettings(),
        api=ApiSettings(),
        storage=StorageSettings(),
    )

    async def mock_query(prompt: Any, options: Any):
        class MockMessage:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class MockTextBlock:
            def __init__(self, text):
                self.text = text

        yield MockMessage(session_id="test-session", type="task_started")
        yield MockMessage(
            session_id="test-session",
            content=[MockTextBlock("Regular text response")],
            type="assistant"
        )
        yield MockMessage(
            session_id="test-session",
            is_error=False,
            result="Done",
            type="result"
        )

    # Patch isinstance checks
    from claude_agent_sdk import AssistantMessage, ResultMessage, TaskStartedMessage, TextBlock

    original_isinstance = isinstance
    def custom_isinstance(obj, classinfo):
        if hasattr(obj, 'type'):
            if classinfo is TaskStartedMessage and obj.type == "task_started":
                return True
            if classinfo is AssistantMessage and obj.type == "assistant":
                return True
            if classinfo is ResultMessage and obj.type == "result":
                return True
            if classinfo is TextBlock and hasattr(obj, 'text'):
                return True
        return original_isinstance(obj, classinfo)

    monkeypatch.setattr("builtins.isinstance", custom_isinstance)
    monkeypatch.setattr("src.agent.executor.query", mock_query)

    result = await execute_agent_message(
        config=config,
        prompt="test",
        cwd=tmp_path,
        # 不传 output_format
    )

    # structured_output 应为 None
    assert result.structured_output is None
