"""Upload batch management service."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, UploadFile

from app.config import WorkspaceSettings
from app.schemas.file import UploadBatchFile, UploadBatchMetadata

_FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    """文件名安全化处理."""
    raw_name = Path(filename).name.strip()
    if not raw_name:
        return f"file_{uuid.uuid4().hex[:8]}"

    # 移除危险字符
    sanitized = _FILENAME_SAFE_PATTERN.sub("_", raw_name)

    # 防止隐藏文件
    if sanitized.startswith("."):
        sanitized = "file_" + sanitized[1:]

    return sanitized or f"file_{uuid.uuid4().hex[:8]}"


def _compute_sha256(file_obj: BinaryIO) -> str:
    """计算文件 SHA256."""
    sha256 = hashlib.sha256()
    file_obj.seek(0)
    while chunk := file_obj.read(8192):
        sha256.update(chunk)
    file_obj.seek(0)
    return sha256.hexdigest()


class UploadBatchService:
    """上传批次管理服务."""

    def __init__(self, settings: WorkspaceSettings):
        self.settings = settings
        self.workspace_root = Path(settings.workspace_root)
        self.batch_root = self.workspace_root / settings.upload_batch_dir

        # 确保目录存在
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.batch_root.mkdir(parents=True, exist_ok=True)

    async def create_batch(self, files: list[UploadFile]) -> UploadBatchMetadata:
        """创建上传批次.

        Args:
            files: 上传的文件列表

        Returns:
            批次元数据

        Raises:
            HTTPException: 文件验证失败
        """
        # 验证文件数量
        if len(files) > self.settings.max_batch_files:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "TOO_MANY_FILES",
                    "message": f"Maximum {self.settings.max_batch_files} files per batch",
                },
            )

        # 生成批次 ID
        batch_id = f"ub_{uuid.uuid4().hex}"
        batch_dir = self.batch_root / batch_id
        files_dir = batch_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        # 处理每个文件
        batch_files: list[UploadBatchFile] = []
        total_size = 0

        for upload in files:
            if not upload.filename:
                await upload.close()
                continue

            # 验证文件类型
            if upload.content_type not in self.settings.allowed_content_types:
                await upload.close()
                shutil.rmtree(batch_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "INVALID_FILE_TYPE",
                        "message": f"File type {upload.content_type} not allowed",
                        "details": {"filename": upload.filename},
                    },
                )

            # 读取文件内容
            content = await upload.read()
            file_size = len(content)

            # 验证文件大小
            if file_size > self.settings.max_file_size:
                await upload.close()
                shutil.rmtree(batch_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "FILE_TOO_LARGE",
                        "message": f"File size ({file_size} bytes) exceeds limit ({self.settings.max_file_size} bytes)",
                        "details": {"filename": upload.filename, "size": file_size},
                    },
                )

            total_size += file_size

            # 验证批次总大小
            if total_size > self.settings.max_batch_size:
                await upload.close()
                shutil.rmtree(batch_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "BATCH_TOO_LARGE",
                        "message": f"Total batch size ({total_size} bytes) exceeds limit ({self.settings.max_batch_size} bytes)",
                    },
                )

            # 生成文件 ID 和安全文件名
            file_id = f"file_{uuid.uuid4().hex[:12]}"
            safe_name = _sanitize_filename(upload.filename)
            stored_name = f"{file_id}__{safe_name}"

            # 保存文件
            file_path = files_dir / stored_name
            file_path.write_bytes(content)

            # 计算哈希
            sha256 = hashlib.sha256(content).hexdigest()

            # 记录文件信息
            batch_files.append(
                UploadBatchFile(
                    file_id=file_id,
                    original_filename=upload.filename,
                    safe_filename=safe_name,
                    stored_name=stored_name,
                    content_type=upload.content_type,
                    size=file_size,
                    sha256=sha256,
                )
            )

            await upload.close()

        # 创建批次元数据
        expires_at = datetime.utcnow() + timedelta(hours=self.settings.batch_ttl_hours)
        metadata = UploadBatchMetadata(
            upload_batch_id=batch_id,
            status="pending",
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            files=batch_files,
        )

        # 保存元数据
        manifest_path = batch_dir / "manifest.json"
        manifest_path.write_text(
            metadata.model_dump_json(indent=2, exclude_none=False),
            encoding="utf-8",
        )

        return metadata

    def get_batch(self, batch_id: str) -> UploadBatchMetadata:
        """获取批次元数据.

        Args:
            batch_id: 批次 ID

        Returns:
            批次元数据

        Raises:
            HTTPException: 批次不存在
        """
        batch_dir = self.batch_root / batch_id
        manifest_path = batch_dir / "manifest.json"

        if not manifest_path.exists():
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "BATCH_NOT_FOUND",
                    "message": f"Upload batch {batch_id} not found",
                },
            )

        return UploadBatchMetadata.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    def update_batch_status(
        self,
        batch_id: str,
        status: str,
        session_id: str | None = None,
    ) -> UploadBatchMetadata:
        """更新批次状态.

        Args:
            batch_id: 批次 ID
            status: 新状态
            session_id: 绑定的会话 ID（可选）

        Returns:
            更新后的批次元数据
        """
        metadata = self.get_batch(batch_id)
        metadata.status = status  # type: ignore

        if session_id:
            metadata.bound_session_id = session_id

        manifest_path = self.batch_root / batch_id / "manifest.json"
        manifest_path.write_text(
            metadata.model_dump_json(indent=2, exclude_none=False),
            encoding="utf-8",
        )

        return metadata

    def consume_batch(self, batch_id: str, session_id: str) -> UploadBatchMetadata:
        """消费批次（标记为已绑定）.

        Args:
            batch_id: 批次 ID
            session_id: 会话 ID

        Returns:
            更新后的批次元数据

        Raises:
            HTTPException: 批次状态不允许消费
        """
        metadata = self.get_batch(batch_id)

        if metadata.status == "consumed":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "BATCH_ALREADY_CONSUMED",
                    "message": f"Upload batch {batch_id} has already been consumed",
                    "details": {"bound_session_id": metadata.bound_session_id},
                },
            )

        if metadata.status == "expired":
            raise HTTPException(
                status_code=410,
                detail={
                    "code": "BATCH_EXPIRED",
                    "message": f"Upload batch {batch_id} has expired",
                },
            )

        if metadata.status == "deleted":
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "BATCH_DELETED",
                    "message": f"Upload batch {batch_id} has been deleted",
                },
            )

        return self.update_batch_status(batch_id, "consumed", session_id)

    def delete_batch(self, batch_id: str) -> None:
        """删除批次.

        Args:
            batch_id: 批次 ID

        Raises:
            HTTPException: 批次已被消费或不存在
        """
        metadata = self.get_batch(batch_id)

        if metadata.status == "consumed":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "BATCH_ALREADY_CONSUMED",
                    "message": "Cannot delete a consumed batch",
                },
            )

        batch_dir = self.batch_root / batch_id
        shutil.rmtree(batch_dir, ignore_errors=True)

    def get_batch_files_dir(self, batch_id: str) -> Path:
        """获取批次文件目录.

        Args:
            batch_id: 批次 ID

        Returns:
            文件目录路径
        """
        return self.batch_root / batch_id / "files"

    def cleanup_expired_batches(self) -> int:
        """清理过期批次.

        Returns:
            清理的批次数量
        """
        now = datetime.utcnow()
        cleaned = 0

        for batch_dir in self.batch_root.iterdir():
            if not batch_dir.is_dir():
                continue

            manifest_path = batch_dir / "manifest.json"
            if not manifest_path.exists():
                continue

            try:
                metadata = UploadBatchMetadata.model_validate_json(
                    manifest_path.read_text(encoding="utf-8")
                )

                # 跳过已消费的批次
                if metadata.status == "consumed":
                    continue

                # 检查是否过期
                if metadata.expires_at and metadata.expires_at < now:
                    # 标记为过期
                    metadata.status = "expired"
                    manifest_path.write_text(
                        metadata.model_dump_json(indent=2, exclude_none=False),
                        encoding="utf-8",
                    )
                    # 删除文件（保留 manifest 用于审计）
                    files_dir = batch_dir / "files"
                    if files_dir.exists():
                        shutil.rmtree(files_dir, ignore_errors=True)
                    cleaned += 1
            except Exception:
                continue

        return cleaned
