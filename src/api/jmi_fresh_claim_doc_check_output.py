from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.jmi_intake_checkout_output import extract_first_json_value

STRUCTURED_OUTPUT_PROFILE_JMI_FRESH_CLAIM = "jmi_fresh_claim_doc_check"

DocResult = Literal["pass", "fail", "partial"]
CheckResult = Literal["pass", "fail", "partial"]

# 与 claim-materials-checklist.md 七类中文名一致（documents[].name_zh）
_EXPECTED_DOC_NAMES_ZH: tuple[str, ...] = (
    "事故陈述记录（出险笔录）",
    "事故现场勘察报告 (FCCS)",
    "损伤列表报告/定损单",
    "受保车辆驾驶员陈述书",
    "驾驶执照复印件",
    "车辆登记证副本",
    "事故现场照片证据",
)


def _normalize_name_zh_for_compare(name: str) -> str:
    """
    与 _EXPECTED_DOC_NAMES_ZH 比较用的归一化。
    常见差异：ASCII 括号前多空格或少空格（如「报告 (FCCS)」vs「报告(FCCS)」）。
    """
    s = name.strip()
    return re.sub(r" +(\()", r"\1", s)


class MaterialPresenceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool
    source_files_hint: list[str] = Field(default_factory=list)


class DocumentCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str
    result: CheckResult
    evidence: str
    notes: str | None = None


class FreshClaimDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name_zh: str
    result: DocResult
    checks: list[DocumentCheck]

    @field_validator("checks")
    @classmethod
    def checks_non_empty(cls, v: list[DocumentCheck]) -> list[DocumentCheck]:
        if not v:
            raise ValueError("documents[].checks 不可为空")
        return v


class JmiFreshClaimDocCheckOutput(BaseModel):
    """与 .claude/skills/jmi-fresh-claim-doc-check/references/output-schema.md 对齐。"""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    checklist: Literal["fresh_claim_documents"] = "fresh_claim_documents"
    reference_policy: str
    vision_pipeline: dict[str, Any]
    policy_snapshot: dict[str, Any]
    material_presence: dict[str, MaterialPresenceEntry]
    overall_result: DocResult
    overall_summary_zh: str
    documents: list[FreshClaimDocument]
    recommended_actions_zh: list[str]

    @field_validator("documents")
    @classmethod
    def seven_docs_ids_and_names(cls, v: list[FreshClaimDocument]) -> list[FreshClaimDocument]:
        if len(v) != 7:
            msg = f"documents 须含 7 项 fresh claim 材料，当前 {len(v)} 项"
            raise ValueError(msg)
        for i, doc in enumerate(v):
            exp_id = i + 1
            if doc.id != exp_id:
                msg = f"documents[{i}].id 须为 {exp_id}，实际 {doc.id}"
                raise ValueError(msg)
            exp_name = _EXPECTED_DOC_NAMES_ZH[i]
            if _normalize_name_zh_for_compare(doc.name_zh) != _normalize_name_zh_for_compare(
                exp_name
            ):
                msg = f"documents[{i}].name_zh 须为 {exp_name!r}，实际 {doc.name_zh!r}"
                raise ValueError(msg)
        return v


def parse_jmi_fresh_claim_doc_check_final_answer(
    text: str,
) -> tuple[JmiFreshClaimDocCheckOutput | None, str | None]:
    """
    解析 Agent 最终回复为 JMI fresh claim 文档质检结构化结果。
    成功返回 (model, None)；失败返回 (None, 人类可读错误)。
    """
    raw, err = extract_first_json_value(text)
    if err:
        return None, err
    if not isinstance(raw, dict):
        return None, "顶层 JSON 必须是对象"
    try:
        return JmiFreshClaimDocCheckOutput.model_validate(raw), None
    except Exception as exc:  # ValidationError 等
        return None, f"JSON 未通过 fresh_claim_doc_check 模式校验: {exc}"
