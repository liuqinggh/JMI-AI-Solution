"""jmi_fresh_claim_doc_check 最终答案 JSON 解析与 Pydantic 校验。"""
from __future__ import annotations

import json
from pathlib import Path

from src.api.jmi_fresh_claim_doc_check_output import (
    parse_jmi_fresh_claim_doc_check_final_answer,
)

GOLDEN = (
    Path(__file__).resolve().parent
    / "jmi-fresh-claim-doc-check"
    / "cases"
    / "fnol-0001-6805-03399"
    / "output"
    / "fresh-claim-doc-check-result.json"
)


def test_parse_golden_round_trip() -> None:
    text = GOLDEN.read_text(encoding="utf-8")
    parsed, err = parse_jmi_fresh_claim_doc_check_final_answer(text)
    assert err is None
    assert parsed is not None
    assert parsed.checklist == "fresh_claim_documents"
    assert len(parsed.documents) == 7
    again, err2 = parse_jmi_fresh_claim_doc_check_final_answer(
        json.dumps(parsed.model_dump(), ensure_ascii=False)
    )
    assert err2 is None
    assert again is not None


def test_parse_wrapped_in_fence() -> None:
    inner = GOLDEN.read_text(encoding="utf-8")
    wrapped = f"说明\n```json\n{inner}\n```\n"
    parsed, err = parse_jmi_fresh_claim_doc_check_final_answer(wrapped)
    assert err is None
    assert parsed is not None


def test_parse_bad_documents_count() -> None:
    obj = json.loads(GOLDEN.read_text(encoding="utf-8"))
    obj["documents"] = obj["documents"][:3]
    parsed, err = parse_jmi_fresh_claim_doc_check_final_answer(json.dumps(obj, ensure_ascii=False))
    assert parsed is None
    assert err is not None
    assert "7" in err or "documents" in err.lower()


def test_parse_wrong_name_zh() -> None:
    obj = json.loads(GOLDEN.read_text(encoding="utf-8"))
    obj["documents"][0]["name_zh"] = "错误名称"
    parsed, err = parse_jmi_fresh_claim_doc_check_final_answer(json.dumps(obj, ensure_ascii=False))
    assert parsed is None
    assert err is not None


def test_parse_fccs_name_zh_tolerates_missing_space_before_paren() -> None:
    """模型常输出「事故现场勘察报告(FCCS)」，与规范「事故现场勘察报告 (FCCS)」应视为等同。"""
    obj = json.loads(GOLDEN.read_text(encoding="utf-8"))
    obj["documents"][1]["name_zh"] = "事故现场勘察报告(FCCS)"
    parsed, err = parse_jmi_fresh_claim_doc_check_final_answer(json.dumps(obj, ensure_ascii=False))
    assert err is None
    assert parsed is not None
