---
name: document-ocr-ai
description: OCR 服务，用于识别用户提供的图片或文档内容。当用户需要从图片、PDF 等文件中提取文字或结构化信息时使用；支持 KTP（印尼身份证）、死亡证明、医疗单、警察报告、Traveloka 等预设及通用 Document AI processor，图片/文件由用户提供。
---

# Document OCR AI

使用 Google Document AI 对用户提供的图片或 PDF 做 OCR，通过本 skill 提供的 **Python 脚本** 调用，支持 KTP（印尼身份证）与通用 processor。

## 前置条件

- 已安装 `gcloud` CLI，并执行 `gcloud auth application-default login`
- 使用 KTP 或 axinan-prod 的 processor 前执行：`gcloud config set project axinan-prod`（见 [references/gcp-multi-project.md](references/gcp-multi-project.md)）
- Python 依赖：`google-cloud-documentai`

## 脚本用法

入口：`scripts/documentAI_sample.py`

| 参数 | 说明 |
|------|------|
| `-f` / `--file` | 必填。待处理文件路径（图片或 PDF） |
| `-p` / `--processor-id` | Document AI Processor ID（与 `--ktp`/`--preset` 二选一） |
| `--ktp` | KTP（印尼身份证），等价于 `--preset ktp`，见 [references/ktp-recognition.md](references/ktp-recognition.md) |
| `--preset` | 预设名称（如 death_certificate、medical_bill 等），完整列表见 [references/document-ai-processors.md](references/document-ai-processors.md) |
| `--project-id` | 可选，默认 `660077994974` |
| `--location` | 可选，默认 `us` |
| `--output` | 可选：`text` / `entities` / `both`，默认 `both` |

**KTP 识别（最简）：**

```bash
python scripts/documentAI_sample.py -f /path/to/KTP.jpg --ktp
```

**通用 processor（需已知 processor-id）：**

```bash
python scripts/documentAI_sample.py -f /path/to/doc.pdf -p <PROCESSOR_ID>
```

**其他预设（死亡证明、医疗单、警察报告、Traveloka 等）：** 见 [references/document-ai-processors.md](references/document-ai-processors.md)，使用 `--preset <name>`。

输出：文档全文和/或实体 JSON（KTP 为姓名、证件号等结构化字段）。

## 流程

1. 确认用户已提供待识别文件路径。
2. **KTP**：`--ktp` 或 `--preset ktp`；**其他预设**：`--preset <name>`（见 [references/document-ai-processors.md](references/document-ai-processors.md)）；**自定义**：`-p <PROCESSOR_ID>`。
3. 将脚本输出的全文或实体返回用户。
