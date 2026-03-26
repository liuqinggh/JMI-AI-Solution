---
name: image-by-intent
description: Identify or extract image or PDF content according to user intent. Use when the user wants the model to read an image or PDF and respond to a specific request—e.g. "根据这张图做X", "识别图片/PDF里的表格", "把截图/PDF转成笔记", "描述图片/文档内容"—via local LiteLLM (curl/script, no GUI). Supports PNG/JPEG/WebP and PDF; Gemini 原生支持 PDF，无需转图。User intent as prompt; default when none given.
---

# Image by Intent

根据用户意图识别并输出图片或 PDF 内容：用户可指定要做什么（描述、摘录表格、转笔记等），未指定时使用默认「识别并描述内容」。支持**图片**（PNG/JPEG/WebP）与 **PDF**；Gemini 原生支持 PDF 文件，**无需将 PDF 转为图片**。通过本地 LiteLLM + curl 调用，无需第三方 API Key。

## Quick start

**逻辑**：以**用户意图**驱动——用户提供 prompt 时用该意图处理内容，未提供时使用默认 prompt。**path** 可为目录、单张图片或单个 PDF；PDF 整份以 `application/pdf` 直接发给模型，不转图。

```bash
# 目录（图片 + PDF 均会处理）
./scripts/vision-curl.sh /path/to/folder
./scripts/vision-curl.sh /path/to/folder "请描述图中的表格并输出为 Markdown。"

# 单张图片
./scripts/vision-curl.sh /path/to/screenshot.png "把截图转成会议纪要风格的笔记。"

# 单个 PDF（整份一次发送，Gemini 原生处理）
./scripts/vision-curl.sh /path/to/doc.pdf
./scripts/vision-curl.sh /path/to/doc.pdf "提取文档中的关键结论。"
```

依赖：`jq`、`curl`。图片支持 PNG/JPEG/WebP；PDF 由 Gemini 原生支持，无需额外依赖（如 poppler）。

## Env (可选)

| Env | 默认 | 说明 |
|-----|------|------|
| `LITELLM_BASE_URL` | `http://localhost:4000/v1` | LiteLLM OpenAI 兼容地址 |
| `LITELLM_MODEL` | `gemini-2.5-flash` | 视觉模型 id（与 `/v1/models` 一致） |
| `IMAGE_PROMPT` | （无） | 若设置，作为**用户意图**替换默认 prompt；未设置则用脚本默认或命令行第二参数 |

## 单张图片 curl 示例

一次处理一张图。`PROMPT` 即用户意图；**用户有具体意图时应替换为对应指令**，无则用默认。

```bash
IMG="/path/to/image.png"
B64=$(base64 -i "$IMG" | tr -d '\n')
# 默认意图：识别并描述内容（用户未指定时使用）
PROMPT="请识别这张图片的内容并描述：主要对象、文字（如有）和关键信息。"
curl -s http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg b64 "$B64" --arg prompt "$PROMPT" '{
    model: "gemini-2.5-flash",
    messages: [{
      role: "user",
      content: [
        { type: "text", text: $prompt },
        { type: "image_url", image_url: { url: ("data:image/png;base64," + $b64) } }
      ]
    }
  }')" | jq -r '.choices[0].message.content'
```

JPEG 将 URL 改为 `data:image/jpeg;base64,...`。确保本机 LiteLLM 已启动且模型支持视觉输入。
