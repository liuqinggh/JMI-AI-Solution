from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import UploadSettings
from app.models.upload import StoredUpload

FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    raw_name = Path(filename).name.strip()
    if not raw_name:
        return f"file_{uuid.uuid4().hex[:8]}"
    sanitized = FILENAME_SAFE_PATTERN.sub("_", raw_name)
    if sanitized.startswith("."):
        sanitized = f"file{sanitized}"
    return sanitized or f"file_{uuid.uuid4().hex[:8]}"


class UploadService:
    def __init__(self, settings: UploadSettings, root: Path | None = None):
        self.settings = settings
        self.root = root or Path.cwd()
        self.temp_dir = self.root / settings.temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size_bytes = settings.max_file_size_mb * 1024 * 1024
        self.allowed_extensions = {ext.lower() for ext in settings.allowed_extensions}

    async def save_files(self, files: list[UploadFile]) -> list[StoredUpload]:
        stored: list[StoredUpload] = []
        for upload in files:
            original_name = upload.filename or ""
            suffix = Path(original_name).suffix.lower()
            if suffix not in self.allowed_extensions:
                raise HTTPException(status_code=400, detail="File extension is not allowed")

            content = await upload.read()
            size = len(content)
            if size > self.max_file_size_bytes:
                raise HTTPException(status_code=413, detail="File size exceeds configured limit")

            file_id = f"file_{uuid.uuid4().hex[:12]}"
            safe_name = sanitize_filename(original_name)
            relative_path = Path(self.settings.temp_dir) / f"{file_id}_{safe_name}"
            absolute_path = self.root / relative_path
            absolute_path.parent.mkdir(parents=True, exist_ok=True)
            absolute_path.write_bytes(content)

            stored.append(
                StoredUpload(
                    file_id=file_id,
                    original_name=original_name,
                    saved_path=str(relative_path),
                    size=size,
                    content_type=upload.content_type or "application/octet-stream",
                )
            )
            (self.temp_dir / f"{file_id}.json").write_text(
                stored[-1].model_dump_json(indent=2),
                encoding="utf-8",
            )
            await upload.close()

        return stored

    def get_file(self, file_id: str) -> StoredUpload:
        metadata_path = self.temp_dir / f"{file_id}.json"
        if not metadata_path.exists():
            raise HTTPException(status_code=404, detail=f"Uploaded file '{file_id}' not found")
        return StoredUpload.model_validate_json(metadata_path.read_text(encoding="utf-8"))
