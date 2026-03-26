#!/usr/bin/env python3
"""
Document AI 命令行工具：对单个文件调用 process_document，mime_type 随文件自动推断。
用法示例:
  python documentAI_sample.py --file /path/to/doc.pdf --processor-id xxx
  python documentAI_sample.py -f image.jpg -p xxx --project-id 660077994974 --location us
  python documentAI_sample.py -f KTP.jpg --ktp
  python documentAI_sample.py -f doc.pdf --preset death_certificate
"""

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

from google.cloud import documentai
from google.cloud.documentai_v1 import Document

# 凭证路径：固定使用 gcloud ADC 文件，与 notebook 一致
CREDENTIALS_PATH = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")

# 预设 processor（project 660077994974, location us），详见 references/document-ai-processors.md
PRESETS = {
    "ktp": "10dee3ae32570cdf",
    "death_certificate": "b55397f6cb350861",
    "identifier_classifier": "148acbbd72e20e4b",
    "medical_bill": "229170d253e069b6",
    "police_report": "ca0026f3dc9b92f7",
    "traveloka_delay": "d2a8bd41f571631c",
    "traveloka_classifier": "74a98509ba0fac75",
}


def process_document_sample(
    project_id: str,
    location: str,
    processor_id: str,
    file_path: str,
    mime_type: str = "application/octet-stream",
) -> Document:
    if os.path.isfile(CREDENTIALS_PATH):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(CREDENTIALS_PATH)
    client = documentai.DocumentProcessorServiceClient()
    name = client.processor_path(project_id, location, processor_id)

    with open(file_path, "rb") as f:
        content = f.read()

    raw_document = documentai.RawDocument(content=content, mime_type=mime_type)
    request = documentai.ProcessRequest(name=name, raw_document=raw_document)
    result = client.process_document(request=request)
    return result.document


def extract_entities(document: Document) -> dict:
    entities = document.entities
    entities_dict = {}
    for entity in entities:
        entity_type = entity.type_
        value = entity.mention_text or (
            entity.text_anchor.content if entity.text_anchor else ""
        )
        entities_dict[entity_type] = value
    return entities_dict


def guess_mime_type(file_path: str) -> str:
    """根据文件路径推断 mime_type，猜不到则用 application/octet-stream。"""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = "application/octet-stream"
    return mime_type


def main():
    parser = argparse.ArgumentParser(
        description="Document AI: 对单个文件执行 process_document，mime_type 随文件自动推断。"
    )
    parser.add_argument(
        "-f", "--file",
        required=True,
        help="待处理的文件路径（图片或 PDF 等）",
    )
    parser.add_argument(
        "-p", "--processor-id",
        dest="processor_id",
        help="Document AI Processor ID（使用 --ktp 时可省略）",
    )
    parser.add_argument(
        "--ktp",
        action="store_true",
        help="使用 KTP（印尼身份证）processor，等价于 --preset ktp",
    )
    parser.add_argument(
        "--preset",
        choices=list(PRESETS),
        metavar="NAME",
        help="预设 processor 名称（见 references/document-ai-processors.md）；与 --ktp 二选一或与 -p 二选一",
    )
    parser.add_argument(
        "--project-id",
        default="660077994974",
        help="GCP 项目 ID（默认: 660077994974）",
    )
    parser.add_argument(
        "--location",
        default="us",
        help="Processor 所在 region（默认: us）",
    )
    parser.add_argument(
        "--output",
        choices=["text", "entities", "both"],
        default="both",
        help="输出内容：text=仅全文，entities=仅实体 JSON，both=两者（默认）",
    )
    args = parser.parse_args()

    if args.ktp:
        args.preset = "ktp"
    if getattr(args, "preset", None):
        args.processor_id = PRESETS[args.preset]
        args.project_id = "660077994974"
        args.location = "us"
    if not args.processor_id:
        parser.error("必须指定 --processor-id、--ktp 或 --preset")

    file_path = args.file
    if not Path(file_path).is_file():
        print(f"错误: 文件不存在: {file_path}", file=sys.stderr)
        sys.exit(1)

    mime_type = guess_mime_type(file_path)
    if args.output != "entities":
        print(f"文件: {file_path}", file=sys.stderr)
        print(f"MIME: {mime_type}", file=sys.stderr)

    try:
        doc = process_document_sample(
            project_id=args.project_id,
            location=args.location,
            processor_id=args.processor_id,
            file_path=file_path,
            mime_type=mime_type,
        )
    except Exception as e:
        print(f"处理失败: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output in ("text", "both") and doc.text:
        print("--- 文档全文 ---")
        print(doc.text.strip())

    if args.output in ("entities", "both") and doc.entities:
        entities = extract_entities(doc)
        print("--- 实体 JSON ---")
        print(json.dumps(entities, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
