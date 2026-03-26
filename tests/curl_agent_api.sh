#!/usr/bin/env bash
# JMI fresh claim 文档质检：multipart 上传保单 Markdown + materials 目录下全部 PDF，
# 并启用 structured_output_profile=jmi_fresh_claim_doc_check（服务端 Pydantic 校验后返回精简 JSON）。
#
# 用法（在 agent-sdk-api-service 仓库内任意目录执行均可）：
#   ./scripts/curl_agent_api.sh
# 环境变量：
#   AGENT_API_BASE_URL   默认 http://127.0.0.1:8000
#   JMI_FRESH_CLAIM_CASE_DIR  案件目录，默认 tests/jmi-fresh-claim-doc-check/cases/fnol-0001-6805-03399
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE_URL="${AGENT_API_BASE_URL:-http://127.0.0.1:8000}"
BASE_URL="${BASE_URL%/}"

CASE_DIR="${JMI_FRESH_CLAIM_CASE_DIR:-tests/jmi-fresh-claim-doc-check/cases/fnol-0001-6805-03399}"
POLICY="${CASE_DIR}/input/policy.md"
MATERIALS_GLOB="${CASE_DIR}/input/materials"/*.pdf

if [[ ! -f "$POLICY" ]]; then
  echo "错误: 未找到保单文件: $ROOT/$POLICY" >&2
  exit 2
fi

shopt -s nullglob
pdf_files=($MATERIALS_GLOB)
shopt -u nullglob
if [[ ${#pdf_files[@]} -eq 0 ]]; then
  echo "错误: 未找到 PDF: $ROOT/${CASE_DIR}/input/materials/*.pdf" >&2
  exit 3
fi

PROMPT="使用 jmi-fresh-claim-doc-check 技能：请严格按技能检查清单与 OCR 容差规则，对已上传的 policy.md（保单）及同批上传的理赔 PDF 做 fresh claim 文档质检。
case_id 必须为 \"FNOL_0001_6805_03399\"。
输出要求：仅输出一段合法 JSON（不要用 markdown 代码围栏），顶层字段需包含：case_id、checklist、reference_policy、vision_pipeline、policy_snapshot、material_presence、overall_result、overall_summary_zh、documents、recommended_actions_zh；其中 documents 为 7 项，id 1–7，与技能 references/output-schema.md 一致。"

curl_args=(
  -sS -X POST "${BASE_URL}/v1/agent/messages"
  -F "prompt=${PROMPT}"
  -F "files=@${POLICY};type=text/markdown"
  -F "structured_output_profile=jmi_fresh_claim_doc_check"
)
for f in "${pdf_files[@]}"; do
  curl_args+=(-F "files=@${f};type=application/pdf")
done

curl "${curl_args[@]}"
