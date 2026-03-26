"""Schema Registry - 映射 structured_output_profile 到 Pydantic Model。"""
from __future__ import annotations

from typing import Any

from src.api.jmi_fresh_claim_doc_check_output import JmiFreshClaimDocCheckOutput
from src.api.jmi_intake_checkout_output import JmiIntakeCallCheckoutOutput

# Schema 映射表：profile 名称 → Pydantic Model
SCHEMA_MAP: dict[str, type] = {
    "jmi_intake_call_checkout": JmiIntakeCallCheckoutOutput,
    "jmi_fresh_claim_doc_check": JmiFreshClaimDocCheckOutput,
}


def get_output_format(profile: str | None) -> dict[str, Any] | None:
    """
    根据 structured_output_profile 动态生成 output_format。

    Args:
        profile: structured_output_profile 名称（如 "jmi_intake_call_checkout"）

    Returns:
        output_format dict 用于 ClaudeAgentOptions，格式：
        {
            "type": "json_schema",
            "schema": <Pydantic Model 的 JSON Schema>
        }
        如果 profile 为 None 或未知，返回 None。
    """
    p = (profile or "").strip()
    if not p:
        return None

    schema_model = SCHEMA_MAP.get(p)
    if not schema_model:
        return None

    return {
        "type": "json_schema",
        "schema": schema_model.model_json_schema(),
    }
