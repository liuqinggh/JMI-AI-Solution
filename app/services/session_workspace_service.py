"""Session workspace management service."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from app.config import WorkspaceSettings
from app.schemas.file import SessionFileMetadata, SessionManifest
from app.services.upload_batch_service import UploadBatchService


class SessionWorkspaceService:
    """会话工作区管理服务."""

    def __init__(self, settings: WorkspaceSettings, batch_service: UploadBatchService):
        self.settings = settings
        self.batch_service = batch_service

        self.workspace_root = Path(settings.workspace_root)
        self.pending_root = self.workspace_root / settings.pending_workspace_dir
        self.session_root = self.workspace_root / settings.session_dir

        # 确保目录存在
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.pending_root.mkdir(parents=True, exist_ok=True)
        self.session_root.mkdir(parents=True, exist_ok=True)

    def create_pending_workspace(self, request_id: str | None = None) -> Path:
        """创建待处理工作区.

        Args:
            request_id: 可选的请求 ID，未提供则自动生成

        Returns:
            工作区路径
        """
        if request_id is None:
            request_id = f"req_{uuid.uuid4().hex}"

        workspace_dir = self.pending_root / request_id
        workspace_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (workspace_dir / "uploads").mkdir(exist_ok=True)
        (workspace_dir / "artifacts").mkdir(exist_ok=True)

        # 创建空的 manifest
        manifest = SessionManifest(
            session_id="",  # 尚未分配
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            files=[],
        )
        manifest_path = workspace_dir / "manifest.json"
        manifest_path.write_text(
            manifest.model_dump_json(indent=2, exclude_none=False),
            encoding="utf-8",
        )

        return workspace_dir

    def import_batch_to_workspace(
        self,
        workspace_dir: Path,
        batch_id: str,
        file_ids: list[str] | None = None,
    ) -> list[SessionFileMetadata]:
        """将批次文件导入工作区.

        Args:
            workspace_dir: 工作区路径
            batch_id: 批次 ID
            file_ids: 可选的文件 ID 列表（仅导入指定文件）

        Returns:
            导入的文件元数据列表
        """
        # 获取批次元数据
        batch_metadata = self.batch_service.get_batch(batch_id)
        batch_files_dir = self.batch_service.get_batch_files_dir(batch_id)

        # 确定要导入的文件
        files_to_import = batch_metadata.files
        if file_ids:
            files_to_import = [f for f in batch_metadata.files if f.file_id in file_ids]

        if not files_to_import:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_FILE_SELECTION",
                    "message": "No valid files to import",
                },
            )

        # 导入文件
        uploads_dir = workspace_dir / "uploads"
        uploads_dir.mkdir(exist_ok=True)

        imported_files: list[SessionFileMetadata] = []

        for batch_file in files_to_import:
            source_path = batch_files_dir / batch_file.stored_name
            if not source_path.exists():
                continue

            # 目标文件名（使用 safe_filename）
            target_path = uploads_dir / batch_file.safe_filename

            # 处理重名
            counter = 1
            while target_path.exists():
                stem = Path(batch_file.safe_filename).stem
                suffix = Path(batch_file.safe_filename).suffix
                target_path = uploads_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            # 复制文件
            shutil.copy2(source_path, target_path)

            # 构建文件元数据
            relative_path = f"./uploads/{target_path.name}"
            imported_files.append(
                SessionFileMetadata(
                    file_id=batch_file.file_id,
                    original_filename=batch_file.original_filename,
                    safe_filename=target_path.name,
                    relative_path=relative_path,
                    download_url="",  # 会在 finalize 时更新
                    content_type=batch_file.content_type,
                    size=batch_file.size,
                    sha256=batch_file.sha256,
                    source_batch_id=batch_id,
                    uploaded_at=datetime.utcnow(),
                )
            )

        # 更新 manifest
        self._update_workspace_manifest(workspace_dir, imported_files)

        return imported_files

    def finalize_pending_workspace(
        self,
        workspace_dir: Path,
        session_id: str,
    ) -> Path:
        """将待处理工作区迁移为会话工作区.

        Args:
            workspace_dir: 待处理工作区路径
            session_id: SDK 返回的会话 ID

        Returns:
            会话工作区路径
        """
        session_dir = self.session_root / session_id

        # 如果会话目录已存在（续接会话），合并内容
        if session_dir.exists():
            self._merge_workspaces(workspace_dir, session_dir)
            shutil.rmtree(workspace_dir, ignore_errors=True)
        else:
            # 原子迁移
            session_dir.parent.mkdir(parents=True, exist_ok=True)
            workspace_dir.rename(session_dir)

        # 更新 manifest 中的 session_id 和 download_url
        self._finalize_manifest(session_dir, session_id)

        return session_dir

    def get_session_workspace(self, session_id: str) -> Path:
        """获取会话工作区路径.

        Args:
            session_id: 会话 ID

        Returns:
            工作区路径

        Raises:
            HTTPException: 会话不存在
        """
        session_dir = self.session_root / session_id

        if not session_dir.exists():
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "SESSION_NOT_FOUND",
                    "message": f"Session {session_id} not found",
                },
            )

        return session_dir

    def get_session_manifest(self, session_id: str) -> SessionManifest:
        """获取会话清单.

        Args:
            session_id: 会话 ID

        Returns:
            会话清单
        """
        session_dir = self.get_session_workspace(session_id)
        manifest_path = session_dir / "manifest.json"

        if not manifest_path.exists():
            # 兼容：如果没有 manifest，返回空清单
            return SessionManifest(
                session_id=session_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                files=[],
            )

        return SessionManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    def list_session_files(self, session_id: str) -> list[SessionFileMetadata]:
        """列出会话的所有文件.

        Args:
            session_id: 会话 ID

        Returns:
            文件元数据列表
        """
        manifest = self.get_session_manifest(session_id)
        return manifest.files

    def get_session_file_path(self, session_id: str, file_id: str) -> Path:
        """获取会话文件的实际路径.

        Args:
            session_id: 会话 ID
            file_id: 文件 ID

        Returns:
            文件路径

        Raises:
            HTTPException: 文件不存在
        """
        manifest = self.get_session_manifest(session_id)
        session_dir = self.get_session_workspace(session_id)

        for file_meta in manifest.files:
            if file_meta.file_id == file_id:
                # relative_path 是 ./uploads/filename
                file_path = session_dir / file_meta.relative_path.lstrip("./")
                if not file_path.exists():
                    raise HTTPException(
                        status_code=404,
                        detail={
                            "code": "FILE_NOT_FOUND",
                            "message": f"File {file_id} not found on disk",
                        },
                    )
                return file_path

        raise HTTPException(
            status_code=404,
            detail={
                "code": "FILE_NOT_FOUND",
                "message": f"File {file_id} not found in session",
            },
        )

    def delete_session_file(self, session_id: str, file_id: str) -> None:
        """删除会话中的文件.

        Args:
            session_id: 会话 ID
            file_id: 文件 ID
        """
        manifest = self.get_session_manifest(session_id)
        session_dir = self.get_session_workspace(session_id)

        # 查找文件
        file_to_delete = None
        for file_meta in manifest.files:
            if file_meta.file_id == file_id:
                file_to_delete = file_meta
                break

        if not file_to_delete:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "FILE_NOT_FOUND",
                    "message": f"File {file_id} not found",
                },
            )

        # 删除物理文件
        file_path = session_dir / file_to_delete.relative_path.lstrip("./")
        file_path.unlink(missing_ok=True)

        # 更新 manifest
        manifest.files = [f for f in manifest.files if f.file_id != file_id]
        manifest.updated_at = datetime.utcnow()

        manifest_path = session_dir / "manifest.json"
        manifest_path.write_text(
            manifest.model_dump_json(indent=2, exclude_none=False),
            encoding="utf-8",
        )

    def delete_session(self, session_id: str) -> None:
        """删除会话工作区.

        Args:
            session_id: 会话 ID
        """
        session_dir = self.session_root / session_id
        shutil.rmtree(session_dir, ignore_errors=True)

    def build_files_context(self, session_id: str) -> str:
        """构建文件上下文（注入到 Agent prompt）.

        Args:
            session_id: 会话 ID

        Returns:
            文件上下文 XML 字符串
        """
        manifest = self.get_session_manifest(session_id)

        if not manifest.files:
            return ""

        file_lines = []
        for file_meta in manifest.files:
            size_mb = file_meta.size / (1024 * 1024)
            file_lines.append(
                f"- {file_meta.safe_filename} ({size_mb:.2f} MB, {file_meta.content_type})\n"
                f"  Path: {file_meta.relative_path}"
            )

        files_list = "\n".join(file_lines)

        return f"""
<uploaded_files>
The following files have been uploaded and are available in this session:

{files_list}

You can read these files using the built-in Read tool with the paths shown above.
Example: Read("{manifest.files[0].relative_path}")
</uploaded_files>
"""

    def _update_workspace_manifest(
        self,
        workspace_dir: Path,
        new_files: list[SessionFileMetadata],
    ) -> None:
        """更新工作区 manifest."""
        manifest_path = workspace_dir / "manifest.json"

        if manifest_path.exists():
            manifest = SessionManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = SessionManifest(
                session_id="",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                files=[],
            )

        # 追加新文件
        manifest.files.extend(new_files)
        manifest.updated_at = datetime.utcnow()

        manifest_path.write_text(
            manifest.model_dump_json(indent=2, exclude_none=False),
            encoding="utf-8",
        )

    def _finalize_manifest(self, session_dir: Path, session_id: str) -> None:
        """完成 manifest（更新 session_id 和 download_url）."""
        manifest_path = session_dir / "manifest.json"

        if not manifest_path.exists():
            return

        manifest = SessionManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        manifest.session_id = session_id
        manifest.updated_at = datetime.utcnow()

        # 更新所有文件的 download_url
        for file_meta in manifest.files:
            file_meta.download_url = f"/api/v1/files/sessions/{session_id}/{file_meta.file_id}"

        manifest_path.write_text(
            manifest.model_dump_json(indent=2, exclude_none=False),
            encoding="utf-8",
        )

    def _merge_workspaces(self, source_dir: Path, target_dir: Path) -> None:
        """合并两个工作区."""
        # 合并 uploads 目录
        source_uploads = source_dir / "uploads"
        target_uploads = target_dir / "uploads"

        if source_uploads.exists():
            target_uploads.mkdir(exist_ok=True)
            for file_path in source_uploads.iterdir():
                if not file_path.is_file():
                    continue

                # 处理重名
                target_path = target_uploads / file_path.name
                counter = 1
                while target_path.exists():
                    stem = file_path.stem
                    suffix = file_path.suffix
                    target_path = target_uploads / f"{stem}_{counter}{suffix}"
                    counter += 1

                shutil.copy2(file_path, target_path)

        # 合并 manifest
        source_manifest_path = source_dir / "manifest.json"
        target_manifest_path = target_dir / "manifest.json"

        if source_manifest_path.exists():
            source_manifest = SessionManifest.model_validate_json(
                source_manifest_path.read_text(encoding="utf-8")
            )

            if target_manifest_path.exists():
                target_manifest = SessionManifest.model_validate_json(
                    target_manifest_path.read_text(encoding="utf-8")
                )
            else:
                target_manifest = SessionManifest(
                    session_id="",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    files=[],
                )

            target_manifest.files.extend(source_manifest.files)
            target_manifest.updated_at = datetime.utcnow()

            target_manifest_path.write_text(
                target_manifest.model_dump_json(indent=2, exclude_none=False),
                encoding="utf-8",
            )
