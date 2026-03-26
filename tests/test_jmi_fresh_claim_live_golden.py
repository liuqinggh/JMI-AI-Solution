"""
JMI fresh claim 文档质检：对已启动的 Agent API 做夹具级联调，并与金样 JSON 比对。

默认 pytest 不运行（避免 CI / 无服务 / 无材料时失败）。需要时：

  JMI_FRESH_CLAIM_LIVE_TEST=1 uv run pytest tests/test_jmi_fresh_claim_live_golden.py -v

可选环境变量：
  AGENT_API_BASE_URL   默认 http://127.0.0.1:8000
  JMI_FRESH_CLAIM_STRICT_GOLDEN=1  规范化后做完整 JSON 深比较（模型未锁定时易失败）
  JMI_FRESH_CLAIM_ASSERT_OVERALL=1  额外断言 overall_result 与金样一致
  JMI_FRESH_CLAIM_HTTP_TIMEOUT     请求超时秒数，默认 900

夹具目录：tests/jmi-fresh-claim-doc-check/cases/<case_id>/manifest.json
需存在 input/materials/*.pdf（与 manifest 中 materials_glob），否则跳过。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
import pytest

LIVE = os.environ.get("JMI_FRESH_CLAIM_LIVE_TEST", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
BASE_URL = os.environ.get("AGENT_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
STRICT = os.environ.get("JMI_FRESH_CLAIM_STRICT_GOLDEN", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
ASSERT_OVERALL = os.environ.get("JMI_FRESH_CLAIM_ASSERT_OVERALL", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

CASES_ROOT = Path(__file__).resolve().parent / "jmi-fresh-claim-doc-check" / "cases"
REQUEST_TIMEOUT_SEC = float(os.environ.get("JMI_FRESH_CLAIM_HTTP_TIMEOUT", "900"))

pytestmark = pytest.mark.skipif(
    not LIVE,
    reason="联调金样测试：设置 JMI_FRESH_CLAIM_LIVE_TEST=1 且启动 API 并补齐夹具材料后再运行",
)


def _list_case_dirs() -> list[Path]:
    if not CASES_ROOT.is_dir():
        return []
    return sorted(p.parent for p in CASES_ROOT.glob("*/manifest.json"))


CASE_DIRS = _list_case_dirs()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_json_object(text: str) -> dict[str, Any]:
    """从 final_answer 中解析 JSON（允许外层 markdown 代码块）。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("final_answer 为空")

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    return json.loads(text)


def _normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    return "".join(c for c in value if c.isdigit())


def _normalize_for_strict_compare(d: dict[str, Any]) -> dict[str, Any]:
    """去掉易随环境变化的字段，便于与人工维护的金样对照。"""
    import copy

    out = copy.deepcopy(d)
    ref = out.get("reference_policy")
    if isinstance(ref, str):
        out["reference_policy"] = Path(ref).name
    vp = out.get("vision_pipeline")
    if isinstance(vp, dict):
        vp = copy.deepcopy(vp)
        vp.pop("litellm_base_url", None)
        vp.pop("model", None)
        out["vision_pipeline"] = vp
    return out


def _build_prompt(case_id: str, policy_filename: str) -> str:
    return (
        f"请严格按项目内 jmi-fresh-claim-doc-check 技能的检查清单与 OCR 容差规则，"
        f"对已上传的 {policy_filename}（保单）及同批上传的理赔 PDF 做 fresh claim 文档质检。\n"
        f'case_id 必须为 "{case_id}"。\n'
        "输出要求：仅输出一段合法 JSON（不要用 markdown 代码围栏），"
        "顶层字段需包含：case_id、checklist、reference_policy、vision_pipeline、"
        "policy_snapshot、material_presence、overall_result、overall_summary_zh、"
        "documents、recommended_actions_zh；其中 documents 为 7 项，id 1–7，"
        "与技能 references/output-schema.md 一致。"
    )


def _assert_structure_against_golden(actual: dict[str, Any], golden: dict[str, Any]) -> None:
    assert actual.get("case_id") == golden.get("case_id")
    assert actual.get("checklist") == golden.get("checklist")

    g_keys = set(golden.get("material_presence", {}))
    a_keys = set(actual.get("material_presence", {}))
    assert a_keys == g_keys, f"material_presence 键不一致: {a_keys ^ g_keys}"

    docs = actual.get("documents")
    assert isinstance(docs, list) and len(docs) == 7
    for i, (a_doc, g_doc) in enumerate(zip(docs, golden["documents"], strict=True), start=1):
        assert a_doc.get("id") == i
        assert g_doc.get("id") == i
        assert a_doc.get("name_zh") == g_doc.get("name_zh")

    snap = actual.get("policy_snapshot")
    g_snap = golden.get("policy_snapshot")
    assert isinstance(snap, dict) and isinstance(g_snap, dict)
    for field in ("policy_number", "chassis", "engine", "insured_id"):
        assert snap.get(field) == g_snap.get(field), f"policy_snapshot.{field} 与金样不一致"
    assert _normalize_phone(snap.get("phone")) == _normalize_phone(g_snap.get("phone"))

    if ASSERT_OVERALL:
        assert actual.get("overall_result") == golden.get("overall_result")


@pytest.mark.parametrize(
    "case_dir",
    CASE_DIRS,
    ids=[p.name for p in CASE_DIRS] if CASE_DIRS else [],
)
def test_jmi_fresh_claim_doc_check_live(case_dir: Path) -> None:
    if not CASE_DIRS:
        pytest.fail("未找到夹具：tests/jmi-fresh-claim-doc-check/cases/*/manifest.json")

    manifest = _load_json(case_dir / "manifest.json")
    inp = manifest["input"]
    policy_path = (case_dir / inp["policy"]).resolve()
    materials_dir = (case_dir / inp["materials_dir"]).resolve()
    glob_pat = inp.get("materials_glob", "*.pdf")
    if not policy_path.is_file():
        pytest.skip(f"缺少保单文件: {policy_path}")
    pdfs = sorted(materials_dir.glob(glob_pat))
    if not pdfs:
        pytest.skip(
            f"缺少材料 PDF（{materials_dir}/{glob_pat}）。请将案件 PDF 放入该目录后再跑联调。"
        )

    golden = _load_json(case_dir / manifest["expected_output"])
    case_id = manifest["case_id"]
    prompt = _build_prompt(case_id, policy_path.name)

    file_fields: list[tuple[str, tuple[str, bytes, str]]] = [
        (
            "files",
            (
                policy_path.name,
                policy_path.read_bytes(),
                "text/markdown",
            ),
        )
    ]
    for pdf in pdfs:
        file_fields.append(("files", (pdf.name, pdf.read_bytes(), "application/pdf")))

    data = {"prompt": prompt}

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SEC) as client:
            r = client.post(f"{BASE_URL}/v1/agent/messages", data=data, files=file_fields)
    except httpx.ConnectError as e:
        pytest.fail(
            f"无法连接 {BASE_URL}，请先启动 API 或设置 AGENT_API_BASE_URL。原因: {e}"
        )

    assert r.status_code == 200, r.text[:2000]
    body = r.json()
    assert body.get("success") is True, body.get("detail", body)

    final = body.get("final_answer")
    try:
        actual = _extract_json_object(final if isinstance(final, str) else "")
    except (json.JSONDecodeError, ValueError) as e:
        pytest.fail(
            f"final_answer 不是合法 JSON: {e}\n---\n{str(final)[:4000] if final else ''}"
        )

    _assert_structure_against_golden(actual, golden)

    if STRICT:
        a_norm = _normalize_for_strict_compare(actual)
        g_norm = _normalize_for_strict_compare(golden)
        assert a_norm == g_norm