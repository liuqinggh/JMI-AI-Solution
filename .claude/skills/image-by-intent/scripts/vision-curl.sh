#!/usr/bin/env bash
# 根据用户意图识别图片或 PDF 内容（本地 LiteLLM，Gemini 原生支持 PDF，无需转图）。
# Usage: vision-curl.sh <path> [prompt]
#   path: 图片目录、单张图片或单个 PDF 文件
#   prompt: 用户意图；不提供则用默认「识别并描述内容」
set -e
PATH_ARG="${1:-.}"
USER_PROMPT="${2:-}"
BASE_URL="${LITELLM_BASE_URL:-http://localhost:4000/v1}"
MODEL="${LITELLM_MODEL:-gemini-2.5-flash}"

if [ -z "$PATH_ARG" ] || [ "$PATH_ARG" = "--help" ] || [ "$PATH_ARG" = "-h" ]; then
  echo "Usage: $0 <path> [prompt]" >&2
  echo "  path:  图片目录、单张图片文件或单个 PDF 文件" >&2
  echo "  prompt: 可选，用户意图；也可通过环境变量 IMAGE_PROMPT 传入（优先）" >&2
  exit 1
fi

DEFAULT_PROMPT="请识别这份内容并描述：主要对象、文字（如有）和关键信息。"
if [ -n "${IMAGE_PROMPT:-}" ]; then
  PROMPT="$IMAGE_PROMPT"
elif [ -n "$USER_PROMPT" ]; then
  PROMPT="$USER_PROMPT"
else
  PROMPT="$DEFAULT_PROMPT"
fi

# 处理单张图片：content 使用 image_url
process_one_image() {
  local img="$1"
  local label="$2"
  local B64_TMP MIME PAYLOAD
  [ -f "$img" ] || return 1
  echo "=== ${label:-$(basename "$img")} ==="
  B64_TMP=$(mktemp)
  trap "rm -f '$B64_TMP'" EXIT
  base64 -i "$img" | tr -d '\n' > "$B64_TMP"
  case "$img" in
    *.[pP][nN][gG]) MIME="image/png" ;;
    *.[jJ][pP][gG]|*.[jJ][pP][eE][gG]) MIME="image/jpeg" ;;
    *.[wW][eE][bB][pP]) MIME="image/webp" ;;
    *) MIME="image/png" ;;
  esac
  PAYLOAD=$(jq -n \
    --arg model "$MODEL" \
    --rawfile b64 "$B64_TMP" \
    --arg mime "$MIME" \
    --arg prompt "$PROMPT" \
    '{
      model: $model,
      messages: [{
        role: "user",
        content: [
          { type: "text", text: $prompt },
          { type: "image_url", image_url: { url: ("data:" + $mime + ";base64," + ($b64 | @text)) } }
        ]
      }]
    }')
  rm -f "$B64_TMP"
  curl -s "$BASE_URL/chat/completions" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" | jq -r '.choices[0].message.content // .error.message // .'
  echo ""
  return 0
}

# 处理单个 PDF：整份 PDF 以 type "file" + file_data 发送，Gemini 原生支持
process_one_pdf() {
  local pdf="$1"
  local label="${2:-$(basename "$pdf")}"
  local B64_TMP PAYLOAD
  [ -f "$pdf" ] || return 1
  echo "=== $label ==="
  B64_TMP=$(mktemp)
  trap "rm -f '$B64_TMP'" EXIT
  base64 -i "$pdf" | tr -d '\n' > "$B64_TMP"
  PAYLOAD=$(jq -n \
    --arg model "$MODEL" \
    --rawfile b64 "$B64_TMP" \
    --arg prompt "$PROMPT" \
    '{
      model: $model,
      messages: [{
        role: "user",
        content: [
          { type: "text", text: $prompt },
          { type: "file", file: { file_data: ("data:application/pdf;base64," + ($b64 | @text)) } }
        ]
      }]
    }')
  rm -f "$B64_TMP"
  curl -s "$BASE_URL/chat/completions" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" | jq -r '.choices[0].message.content // .error.message // .'
  echo ""
  return 0
}

is_image_file() {
  case "$1" in
    *.[pP][nN][gG]|*.[jJ][pP][gG]|*.[jJ][pP][eE][gG]|*.[wW][eE][bB][pP]) return 0 ;;
    *) return 1 ;;
  esac
}

is_pdf_file() {
  case "$1" in
    *.[pP][dD][fF]) return 0 ;;
    *) return 1 ;;
  esac
}

if [ -d "$PATH_ARG" ]; then
  while IFS= read -r -d '' f; do
    [ -f "$f" ] || continue
    if is_image_file "$f"; then
      process_one_image "$f" "$(basename "$f")"
    fi
  done < <(find "$PATH_ARG" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.webp" \) -print0 | sort -z)
  while IFS= read -r -d '' f; do
    [ -f "$f" ] || continue
    process_one_pdf "$f" "$(basename "$f")"
  done < <(find "$PATH_ARG" -maxdepth 1 -type f -iname "*.pdf" -print0 | sort -z)
elif [ -f "$PATH_ARG" ]; then
  if is_image_file "$PATH_ARG"; then
    process_one_image "$PATH_ARG" "$(basename "$PATH_ARG")"
  elif is_pdf_file "$PATH_ARG"; then
    process_one_pdf "$PATH_ARG" "$(basename "$PATH_ARG")"
  else
    echo "不支持的文件类型（仅支持图片 PNG/JPEG/WebP 或 PDF）: $PATH_ARG" >&2
    exit 1
  fi
else
  echo "路径不存在或不可访问: $PATH_ARG" >&2
  exit 1
fi
