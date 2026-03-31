from __future__ import annotations

from pydantic import BaseModel, Field


class StoredUpload(BaseModel):
    file_id: str
    original_name: str
    saved_path: str
    size: int
    content_type: str


class UploadResponse(BaseModel):
    files: list[StoredUpload] = Field(default_factory=list)
