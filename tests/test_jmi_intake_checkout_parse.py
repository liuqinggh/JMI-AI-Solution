from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.api.jmi_intake_checkout_output import (
    extract_first_json_value,
    parse_jmi_intake_checkout_final_answer,
    strip_markdown_json_fence,
)

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = (
    ROOT
    / "tests"
    / "jmi-intake-call-checkout"
    / "cases"
    / "fnol-0001-6805-03399"
    / "output"
    / "intake-checkout-result.json"
)


@pytest.fixture
def golden_obj() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_parse_golden_file_roundtrip(golden_obj: dict) -> None:
    parsed, err = parse_jmi_intake_checkout_final_answer(json.dumps(golden_obj, ensure_ascii=False))
    assert err is None
    assert parsed is not None
    dumped = parsed.model_dump()
    assert dumped["checklist"] == "intake_call_checkout"
    assert len(dumped["items"]) == 4


def test_parse_with_prose_prefix_and_fence(golden_obj: dict) -> None:
    inner = json.dumps(golden_obj, ensure_ascii=False, indent=2)
    wrapped = f'请先确认：以下是结果。\n```json\n{inner}\n```\n谢谢。'
    parsed, err = parse_jmi_intake_checkout_final_answer(wrapped)
    assert err is None
    assert parsed is not None


def test_extract_fails_on_non_json() -> None:
    obj, err = extract_first_json_value("只有中文没有括号")
    assert obj is None
    assert err is not None


def test_parse_validation_items_not_four(golden_obj: dict) -> None:
    bad = {**golden_obj, "items": golden_obj["items"][:3]}
    parsed, err = parse_jmi_intake_checkout_final_answer(json.dumps(bad))
    assert parsed is None
    assert err is not None
    assert "4" in err or "items" in err


def test_parse_rejects_wrong_item_name_en(golden_obj: dict) -> None:
    items = [dict(x) for x in golden_obj["items"]]
    items[0] = {**items[0], "name_en": "wrong_key"}
    bad = {**golden_obj, "items": items}
    parsed, err = parse_jmi_intake_checkout_final_answer(json.dumps(bad))
    assert parsed is None
    assert err is not None
    assert "name_en" in err


def test_parse_rejects_extra_root_key(golden_obj: dict) -> None:
    bad = {**golden_obj, "extra_field": 1}
    parsed, err = parse_jmi_intake_checkout_final_answer(json.dumps(bad))
    assert parsed is None
    assert err is not None


def test_strip_markdown_json_fence_removes_fence() -> None:
    raw = '```json\n{"a":1}\n```'
    assert strip_markdown_json_fence(raw) == '{"a":1}'


def test_strip_markdown_json_fence_preserves_bare_json() -> None:
    raw = '{"a":1}'
    assert strip_markdown_json_fence(raw) == '{"a":1}'


def test_successful_parse_returns_clean_json_roundtrip(golden_obj: dict) -> None:
    """模拟 routes 层逻辑：解析成功后 model_dump_json 产出干净 JSON。"""
    fenced = f'```json\n{json.dumps(golden_obj, ensure_ascii=False)}\n```'
    parsed, err = parse_jmi_intake_checkout_final_answer(fenced)
    assert err is None
    assert parsed is not None
    clean = parsed.model_dump_json(indent=2, exclude_none=False)
    assert not clean.startswith("```")
    reparsed = json.loads(clean)
    assert reparsed["checklist"] == "intake_call_checkout"
