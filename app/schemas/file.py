"""File upload and batch management schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class FileMetadata(BaseModel):
    """单个文件的元数据."""

    file_id: str = Field(..., description="文件唯一 ID")
    original_filename: str = Field(..., description="原始文件名")
    safe_filename: str = Field(..., description="安全化后的文件名")
    content_type: str = Field(..., description="MIME 类型")
    size: int = Field(..., ge=0, description="文件大小（字节）")
    sha256: str | None = Field(None, description="文件 SHA256 哈希")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, description="上传时间")

    @field_validator("original_filename", "safe_filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """验证文件名安全性."""
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("Filename contains invalid characters")
        return v


class UploadBatchFile(BaseModel):
    """上传批次中的文件信息."""

    file_id: str
    original_filename: str
    safe_filename: str
    stored_name: str = Field(..., description="存储文件名（file_id__safe_filename）")
    content_type: str
    size: int
    sha256: str | None = None


class UploadBatchMetadata(BaseModel):
    """上传批次的元数据."""

    upload_batch_id: str
    status: Literal["pending", "consumed", "expired", "deleted"] = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    bound_session_id: str | None = None
    files: list[UploadBatchFile] = Field(default_factory=list)


class SessionFileMetadata(BaseModel):
    """会话中的文件元数据."""

    file_id: str
    original_filename: str
    safe_filename: str
    relative_path: str = Field(..., description="相对于会话工作区的路径")
    download_url: str = Field(..., description="前端下载 URL")
    content_type: str
    size: int
    sha256: str | None = None
    source_batch_id: str | None = Field(None, description="来源批次 ID")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class SessionManifest(BaseModel):
    """会话工作区清单."""

    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    files: list[SessionFileMetadata] = Field(default_factory=list)


# API 响应模型


class UploadBatchFileResponse(BaseModel):
    """上传响应中的文件信息."""

    file_id: str
    filename: str
    content_type: str
    size: int


class UploadBatchResponse(BaseModel):
    """批次上传响应."""

    success: bool = True
    upload_batch_id: str
    status: str
    files: list[UploadBatchFileResponse]


class BatchStatusResponse(BaseModel):
    """批次状态查询响应."""

    upload_batch_id: str
    status: str
    created_at: datetime
    expires_at: datetime | None
    bound_session_id: str | None
    files: list[UploadBatchFile]


class SessionFileListResponse(BaseModel):
    """会话文件列表响应."""

    session_id: str
    total_files: int
    total_size: int
    files: list[SessionFileMetadata]


class DeleteResponse(BaseModel):
    """删除响应."""

    success: bool = True
    message: str


class ErrorDetail(BaseModel):
    """错误详情."""

    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    """错误响应."""

    success: bool = False
    error: ErrorDetail
