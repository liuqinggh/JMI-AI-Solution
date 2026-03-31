from __future__ import annotations

import shutil
from pathlib import Path

from app.core.session_id import validate_business_session_id
from app.models.upload import StoredUpload
from app.services.upload_service import sanitize_filename


class WorkspaceService:
    def __init__(self, root: Path | None = None):
        self.root = root or Path.cwd()

    def prepare_workspace(
        self,
        *,
        business_session_id: str,
        app_cwd: str,
        uploads: list[StoredUpload],
    ) -> tuple[Path, list[str]]:
        cwd = (self.root / app_cwd).resolve()
        safe_session_id = validate_business_session_id(business_session_id)
        upload_dir = cwd / ".agent-platform" / safe_session_id / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        relative_paths: list[str] = []
        for upload in uploads:
            source = self.root / upload.saved_path
            target = upload_dir / sanitize_filename(upload.original_name)
            shutil.copy2(source, target)
            relative_paths.append(str(target.relative_to(cwd)))

        return cwd, relative_paths

    def build_message(self, *, message: str, relative_paths: list[str]) -> str:
        if not relative_paths:
            return message
        file_list = "\n".join(f"- {path}" for path in relative_paths)
        return (
            "以下文件已经放入当前工作目录，可直接使用原生文件工具读取：\n"
            f"{file_list}\n\n"
            f"用户消息：\n{message}"
        )
