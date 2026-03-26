from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OverallResult = Literal["pass", "fail", "partial"]
ItemResult = Literal["pass", "fail", "partial", "needs_review"]
DispatchSurveyor = Literal["required", "not_required", "discretionary"]

# 与 references/output-schema.md「items[]：顺序与固定命名」表一致
_ITEM_ROW_SPECS: tuple[tuple[int, str, str], ...] = (
    (1, "保单号和有效性", "policy_number_and_validity"),
    (2, "姓名和联系电话一致性", "name_and_phone_consistency"),
    (3, "车牌号和车型一致性", "plate_and_vehicle_model_consistency"),
    (4, "事故日期是否在保单有效期内", "loss_date_within_policy_period"),
)


class IntakeCallItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    name_zh: str
    name_en: str
    result: ItemResult
    call_evidence: dict[str, Any] = Field(default_factory=dict)
    policy_evidence: dict[str, Any] = Field(default_factory=dict)
    notes: str


class EmergencyAndSurveyor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_emergency: bool
    emergency_reasons_zh: list[str]
    dispatch_surveyor: DispatchSurveyor
    weighted_total_score: int | float | None = None
    score_breakdown: dict[str, int | None] | None = None
    rationale_zh: str
    remote_survey_options_zh: list[str]
    exceptions_considered_zh: str
    data_gaps: list[str]


class ObservationOutsideChecklist(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    detail: str


class JmiIntakeCallCheckoutOutput(BaseModel):
    """与 .claude/skills/jmi-intake-call-checkout/references/output-schema.md 对齐。"""

    model_config = ConfigDict(extra="forbid")

    case_reference: str = ""
    checklist: Literal["intake_call_checkout"] = "intake_call_checkout"
    source_documents: list[str] = Field(default_factory=list)
    overall_result: OverallResult
    summary: str
    items: list[IntakeCallItem]
    emergency_and_surveyor: EmergencyAndSurveyor
    observations_outside_checklist: list[ObservationOutsideChecklist] | None = None

    @field_validator("items")
    @classmethod
    def items_length_order_and_fixed_names(cls, v: list[IntakeCallItem]) -> list[IntakeCallItem]:
        if len(v) != 4:
            msg = f"items 须含 4 项 intake 核对，当前 {len(v)} 项"
            raise ValueError(msg)
        for i, item in enumerate(v):
            exp_seq, exp_zh, exp_en = _ITEM_ROW_SPECS[i]
            if item.sequence != exp_seq:
                msg = f"items[{i}].sequence 须为 {exp_seq}，实际 {item.sequence}"
                raise ValueError(msg)
            if item.name_zh != exp_zh:
                msg = f"items[{i}].name_zh 须为 {exp_zh!r}，实际 {item.name_zh!r}"
                raise ValueError(msg)
            if item.name_en != exp_en:
                msg = f"items[{i}].name_en 须为 {exp_en!r}，实际 {item.name_en!r}"
                raise ValueError(msg)
        return v


_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def strip_markdown_json_fence(text: str) -> str:
    """若模型仍输出 ```json 包裹，去掉围栏取内层文本。"""
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def extract_first_json_value(text: str) -> tuple[Any | None, str | None]:
    """
    从任意前缀/后缀正文中取出首个可解析的 JSON 值（对象或数组）。
    成功返回 (obj, None)；失败返回 (None, 错误信息)。
    """
    s = strip_markdown_json_fence(text)
    decoder = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch not in "{[":
            continue
        try:
            obj, _end = decoder.raw_decode(s[i:])
        except json.JSONDecodeError as exc:
            return None, f"JSON 解析失败（起始偏移 {i}）: {exc}"
        else:
            return obj, None
    return None, "final_answer 中未找到 JSON 对象或数组"


def parse_jmi_intake_checkout_final_answer(text: str) -> tuple[JmiIntakeCallCheckoutOutput | None, str | None]:
    """
    解析 Agent 最终回复为 JMI intake checkout 结构化结果。
    成功返回 (model, None)；失败返回 (None, 人类可读错误)。
    """
    raw, err = extract_first_json_value(text)
    if err:
        return None, err
    if not isinstance(raw, dict):
        return None, "顶层 JSON 必须是对象"
    try:
        return JmiIntakeCallCheckoutOutput.model_validate(raw), None
    except Exception as exc:  # ValidationError 等
        return None, f"JSON 未通过 intake 模式校验: {exc}"


STRUCTURED_OUTPUT_PROFILE_JMI_INTAKE = "jmi_intake_call_checkout"
