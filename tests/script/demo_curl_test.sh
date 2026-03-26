#!/usr/bin/env bash

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000/v1/agent/messages}"
IMAGE_PATH="${IMAGE_PATH:-/Users/cd-la-067/Downloads/Gemini_Generated_Image_4lw8iw4lw8iw4lw8.png}"
PROMPT="${PROMPT:-请分析这张图片，并总结其中的关键信息。}"
SESSION_ID="${SESSION_ID:-}"

if [[ ! -f "$IMAGE_PATH" ]]; then
  echo "图片不存在: $IMAGE_PATH" >&2
  exit 1
fi

curl_args=(
  --request POST
  --url "$API_URL"
  --form "prompt=$PROMPT"
  --form "files=@${IMAGE_PATH};type=image/png"
)

if [[ -n "$SESSION_ID" ]]; then
  curl_args+=(--form "session_id=$SESSION_ID")
fi

curl "${curl_args[@]}"
echo
