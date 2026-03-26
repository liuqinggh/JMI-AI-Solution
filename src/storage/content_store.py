from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Any

from fastapi import UploadFile

from src.config import StorageSettings


_FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}


class ContentAddressedStore:
    """内容寻址存储，提供去重、会话工作目录和垃圾清理能力。"""

    def __init__(self, settings: StorageSettings):
        self.root = Path(settings.upload_root)
        self.objects_root = self.root / ".objects"
        self.sessions_root = self.root / ".sessions"
        self.pending_root = self.root / settings.pending_dir_name
        self.metadata_root = self.root / ".metadata"

        for directory in (
            self.root,
            self.objects_root,
            self.sessions_root,
            self.pending_root,
            self.metadata_root,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self.refs_db_path = self.metadata_root / "refs.json"
        self.sqlite_path = self.metadata_root / "storage.db"
        self._refs_lock = RLock()
        self._refs_cache: dict[str, dict[str, Any]] | None = None
        self._init_refs_db()
        self._init_sqlite_db()

    def create_pending_dir(self) -> Path:
        pending_dir = self.pending_root / f"req_{uuid.uuid4().hex}"
        pending_dir.mkdir(parents=True, exist_ok=False)
        return pending_dir

    def ensure_session_dir(self, session_id: str) -> Path:
        session_dir = self.sessions_root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        self._sync_session_alias(session_id)
        return session_dir

    def get_session_dir(self, session_id: str) -> Path:
        return self.ensure_session_dir(session_id)

    async def save_uploads(self, files: list[UploadFile], target_dir: Path) -> list[str]:
        saved_names: list[str] = []
        target_dir.mkdir(parents=True, exist_ok=True)
        session_id = self._session_id_for_dir(target_dir)

        for upload in files:
            if not upload.filename:
                await upload.close()
                continue

            temp_path = self._create_temp_path()
            try:
                with temp_path.open("wb") as file_obj:
                    while True:
                        chunk = await upload.read(1024 * 1024)
                        if not chunk:
                            break
                        file_obj.write(chunk)

                content_hash, safe_name = await self.store_file(upload, temp_path)
                link_path = self._create_link_in_dir(
                    target_dir=target_dir,
                    content_hash=content_hash,
                    filename=safe_name,
                    session_id=session_id,
                )
                saved_names.append(link_path.name)
            finally:
                await upload.close()
                temp_path.unlink(missing_ok=True)

        return saved_names

    async def store_file(self, upload: UploadFile, temp_path: Path) -> tuple[str, str]:
        """将临时文件写入对象存储，返回内容 hash 和安全文件名。"""
        safe_name = self._sanitize_filename(upload.filename or "")
        content_hash = self._compute_hash(temp_path)
        object_path = self._get_object_path(content_hash)

        if not object_path.exists():
            shutil.move(str(temp_path), str(object_path))

        self._ensure_object_metadata(
            content_hash=content_hash,
            object_path=object_path,
            filename=safe_name,
        )
        return content_hash, safe_name

    def create_session_link(self, session_id: str, content_hash: str, filename: str) -> Path:
        session_dir = self.ensure_session_dir(session_id)
        return self._create_link_in_dir(
            target_dir=session_dir,
            content_hash=content_hash,
            filename=self._sanitize_filename(filename),
            session_id=session_id,
        )

    def finalize_pending_dir(self, pending_dir: Path, session_id: str) -> Path:
        pending_dir = pending_dir.resolve()
        session_dir = self.sessions_root / session_id

        if pending_dir.exists():
            self._drop_sqlite_directory_refs(pending_dir)
            if session_dir.exists():
                self._merge_directory_contents(pending_dir, session_dir)
                shutil.rmtree(pending_dir, ignore_errors=True)
            else:
                session_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(pending_dir), str(session_dir))

        session_dir.mkdir(parents=True, exist_ok=True)
        self._register_session_links(session_dir, session_id)
        self._sync_session_alias(session_id)
        return session_dir

    def cleanup_session(self, session_id: str) -> None:
        session_dir = self.sessions_root / session_id
        if not session_dir.exists():
            self._remove_session_alias(session_id)
            return

        self._drop_directory_references(
            session_dir,
            session_id=session_id,
            delete_orphans=True,
        )
        shutil.rmtree(session_dir, ignore_errors=True)
        self._remove_session_alias(session_id)

    def cleanup_orphans(self, days: int = 7) -> int:
        cutoff_time = datetime.now() - timedelta(days=days)

        for pending_dir in list(self.pending_root.iterdir()):
            if not pending_dir.is_dir():
                continue
            mtime = datetime.fromtimestamp(pending_dir.stat().st_mtime)
            if mtime >= cutoff_time:
                continue
            self._drop_directory_references(pending_dir, delete_orphans=False)
            shutil.rmtree(pending_dir, ignore_errors=True)

        removed = 0
        with self._refs_lock:
            refs = self._get_refs_locked()
            for content_hash, meta in list(refs.items()):
                if meta.get("ref_count", 0) > 0:
                    continue
                created_at = self._parse_timestamp(meta.get("created_at"))
                if created_at >= cutoff_time:
                    continue
                self._get_object_path(content_hash).unlink(missing_ok=True)
                refs.pop(content_hash, None)
                self._delete_sqlite_object(content_hash)
                removed += 1
            self._persist_refs_locked()

        return removed

    def get_stats(self) -> dict[str, Any]:
        with self._refs_lock, sqlite3.connect(self.sqlite_path) as conn:
            total_objects = int(conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0])
            total_size = int(conn.execute("SELECT COALESCE(SUM(size), 0) FROM objects").fetchone()[0])
            total_refs = int(conn.execute("SELECT COUNT(*) FROM refs").fetchone()[0])
            orphaned = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM objects o
                    LEFT JOIN refs r ON r.content_hash = o.content_hash
                    WHERE r.content_hash IS NULL
                    """
                ).fetchone()[0]
            )
        sessions = sum(1 for item in self.sessions_root.iterdir() if item.is_dir())

        return {
            "total_objects": total_objects,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "total_references": total_refs,
            "orphaned_objects": orphaned,
            "sessions": sessions,
            "dedup_ratio": round(total_refs / total_objects, 2) if total_objects else 0,
        }

    def build_prompt(
        self,
        prompt: str,
        saved_files: list[str],
        template: str,
        target_dir: Path | None = None,
    ) -> str | list[dict[str, Any]]:
        if not saved_files:
            return prompt

        if target_dir is None:
            return template.format(files=", ".join(saved_files), prompt=prompt)

        image_blocks: list[dict[str, Any]] = []
        image_names: list[str] = []
        regular_names: list[str] = []

        for file_name in saved_files:
            mime_type, _ = mimetypes.guess_type(file_name)
            file_path = target_dir / file_name

            if mime_type in _SUPPORTED_IMAGE_MIME_TYPES and file_path.exists():
                image_names.append(file_name)
                image_blocks.append(self._build_image_block(file_path, mime_type))
            else:
                regular_names.append(file_name)

        if not image_blocks:
            return template.format(files=", ".join(saved_files), prompt=prompt)

        instructions: list[str] = []
        if image_names:
            instructions.append(f"用户上传了以下图片：{', '.join(image_names)}")
        if regular_names:
            instructions.append(f"用户还上传了以下文件：{', '.join(regular_names)}")
        instructions.append("")
        instructions.append(prompt)
        instructions.append("")

        if regular_names:
            instructions.append("请直接查看图片内容。对于非图片文件，请使用 Read 工具读取后再回复。")
        else:
            instructions.append("请直接查看图片内容后再回复。")

        return [{"type": "text", "text": "\n".join(instructions)}, *image_blocks]

    def _init_refs_db(self) -> None:
        if not self.refs_db_path.exists():
            self.refs_db_path.write_text("{}", encoding="utf-8")

    def _init_sqlite_db(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS objects (
                    content_hash TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS refs (
                    ref_path TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    session_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(content_hash) REFERENCES objects(content_hash)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_refs_content_hash ON refs(content_hash)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_refs_session_id ON refs(session_id)")
            object_count = int(conn.execute("SELECT COUNT(*) FROM objects").fetchone()[0])
            ref_count = int(conn.execute("SELECT COUNT(*) FROM refs").fetchone()[0])
        if object_count == 0 and ref_count == 0:
            self._rebuild_sqlite_index()

    def _rebuild_sqlite_index(self) -> None:
        existing_meta: dict[str, dict[str, Any]] = {}
        if self.refs_db_path.exists():
            with contextlib.suppress(json.JSONDecodeError):
                existing_meta = json.loads(self.refs_db_path.read_text(encoding="utf-8"))

        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute("DELETE FROM refs")
            conn.execute("DELETE FROM objects")

            for object_path in self.objects_root.rglob("*"):
                if not object_path.is_file():
                    continue
                content_hash = object_path.name
                if not _HASH_PATTERN.match(content_hash):
                    continue
                meta = existing_meta.get(content_hash, {})
                filename = str(meta.get("filename") or content_hash)
                created_at = str(meta.get("created_at") or datetime.now().isoformat())
                conn.execute(
                    """
                    INSERT OR REPLACE INTO objects(content_hash, filename, size, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        content_hash,
                        filename,
                        int(object_path.stat().st_size),
                        created_at,
                    ),
                )

            for ref_path, content_hash in self._iter_object_links(self.pending_root):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO refs(ref_path, content_hash, session_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        self._normalize_ref_path(ref_path),
                        content_hash,
                        None,
                        datetime.now().isoformat(),
                    ),
                )

            for ref_path, content_hash in self._iter_object_links(self.sessions_root):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO refs(ref_path, content_hash, session_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        self._normalize_ref_path(ref_path),
                        content_hash,
                        self._session_id_for_link_path(ref_path),
                        datetime.now().isoformat(),
                    ),
                )

    def _get_refs_locked(self) -> dict[str, dict[str, Any]]:
        if self._refs_cache is None:
            self._refs_cache = json.loads(self.refs_db_path.read_text(encoding="utf-8"))
        return self._refs_cache

    def _persist_refs_locked(self) -> None:
        refs = self._refs_cache if self._refs_cache is not None else {}
        temp_path = self.refs_db_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(refs, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(self.refs_db_path)

    def _ensure_object_metadata(self, content_hash: str, object_path: Path, filename: str) -> None:
        with self._refs_lock:
            refs = self._get_refs_locked()
            meta = refs.setdefault(
                content_hash,
                {
                    "filename": filename,
                    "size": object_path.stat().st_size if object_path.exists() else 0,
                    "created_at": datetime.now().isoformat(),
                    "ref_count": 0,
                    "sessions": [],
                },
            )
            meta["filename"] = meta.get("filename") or filename
            meta["size"] = object_path.stat().st_size if object_path.exists() else int(meta.get("size", 0))
            meta.setdefault("sessions", [])
            meta.setdefault("created_at", datetime.now().isoformat())
            meta.setdefault("ref_count", 0)
            self._persist_refs_locked()
            self._upsert_sqlite_object(
                content_hash=content_hash,
                filename=meta["filename"],
                size=int(meta["size"]),
                created_at=str(meta["created_at"]),
            )

    def _increment_reference(self, content_hash: str, filename: str, session_id: str | None = None) -> None:
        object_path = self._get_object_path(content_hash)
        with self._refs_lock:
            refs = self._get_refs_locked()
            meta = refs.setdefault(
                content_hash,
                {
                    "filename": filename,
                    "size": object_path.stat().st_size if object_path.exists() else 0,
                    "created_at": datetime.now().isoformat(),
                    "ref_count": 0,
                    "sessions": [],
                },
            )
            meta["ref_count"] = int(meta.get("ref_count", 0)) + 1
            meta["filename"] = filename or meta.get("filename", "")
            meta["size"] = object_path.stat().st_size if object_path.exists() else int(meta.get("size", 0))
            sessions = meta.setdefault("sessions", [])
            if session_id and session_id not in sessions:
                sessions.append(session_id)
            self._persist_refs_locked()

    def _register_session_links(self, session_dir: Path, session_id: str) -> None:
        links = self._iter_object_links(session_dir)
        if not links:
            return

        with self._refs_lock:
            refs = self._get_refs_locked()
            for link_path, content_hash in links:
                meta = refs.get(content_hash)
                if meta is None:
                    continue
                sessions = meta.setdefault("sessions", [])
                if session_id not in sessions:
                    sessions.append(session_id)
                self._upsert_sqlite_ref(
                    ref_path=link_path,
                    content_hash=content_hash,
                    session_id=session_id,
                )
            self._persist_refs_locked()

    def _drop_directory_references(
        self,
        directory: Path,
        session_id: str | None = None,
        delete_orphans: bool = False,
    ) -> None:
        links = self._iter_object_links(directory)
        if not links:
            return

        with self._refs_lock:
            refs = self._get_refs_locked()
            for link_path, content_hash in links:
                meta = refs.get(content_hash)
                if meta is None:
                    continue
                meta["ref_count"] = max(0, int(meta.get("ref_count", 0)) - 1)
                sessions = meta.setdefault("sessions", [])
                if session_id and session_id in sessions:
                    sessions.remove(session_id)
                self._delete_sqlite_ref(link_path)
                if delete_orphans and int(meta.get("ref_count", 0)) <= 0:
                    self._get_object_path(content_hash).unlink(missing_ok=True)
                    refs.pop(content_hash, None)
                    self._delete_sqlite_object(content_hash)
            self._persist_refs_locked()

    def _create_link_in_dir(
        self,
        target_dir: Path,
        content_hash: str,
        filename: str,
        session_id: str | None = None,
    ) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        candidate = target_dir / filename
        if candidate.is_symlink() and self._extract_hash_from_link(candidate) == content_hash:
            return candidate
        link_path = self._build_unique_path(target_dir, filename)
        rel_path = os.path.relpath(self._get_object_path(content_hash), start=target_dir)
        link_path.symlink_to(rel_path)
        self._increment_reference(content_hash, filename=filename, session_id=session_id)
        self._upsert_sqlite_ref(
            ref_path=link_path,
            content_hash=content_hash,
            session_id=session_id,
        )
        return link_path

    def _compute_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with file_path.open("rb") as file_obj:
            while chunk := file_obj.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _get_object_path(self, content_hash: str) -> Path:
        shard_dir = self.objects_root / content_hash[:2]
        shard_dir.mkdir(parents=True, exist_ok=True)
        return shard_dir / content_hash

    def _create_temp_path(self) -> Path:
        return self.pending_root / f"upload_{uuid.uuid4().hex}.tmp"

    def _sanitize_filename(self, filename: str) -> str:
        raw_name = Path(filename).name.strip()
        if not raw_name:
            return f"upload_{uuid.uuid4().hex[:8]}"
        sanitized = _FILENAME_SAFE_PATTERN.sub("_", raw_name)
        return sanitized or f"upload_{uuid.uuid4().hex[:8]}"

    def _build_unique_path(self, directory: Path, filename: str) -> Path:
        candidate = directory / filename
        if not candidate.exists() and not candidate.is_symlink():
            return candidate

        stem = Path(filename).stem
        suffix = Path(filename).suffix
        return directory / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"

    def _build_image_block(self, file_path: Path, mime_type: str) -> dict[str, Any]:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": base64.b64encode(file_path.read_bytes()).decode("ascii"),
            },
        }

    def _session_id_for_dir(self, target_dir: Path) -> str | None:
        with contextlib.suppress(FileNotFoundError):
            resolved_dir = target_dir.resolve()
            if resolved_dir.parent == self.sessions_root.resolve():
                return resolved_dir.name
        return None

    def _merge_directory_contents(self, source_dir: Path, target_dir: Path) -> None:
        target_dir.mkdir(parents=True, exist_ok=True)
        for child in source_dir.iterdir():
            destination = self._build_unique_path(target_dir, child.name)
            shutil.move(str(child), str(destination))

    def _iter_object_links(self, directory: Path) -> list[tuple[Path, str]]:
        if not directory.exists():
            return []

        links: list[tuple[Path, str]] = []
        for candidate in directory.rglob("*"):
            if not candidate.is_symlink():
                continue
            content_hash = self._extract_hash_from_link(candidate)
            if content_hash is None:
                continue
            links.append((candidate, content_hash))
        return links

    def _extract_hash_from_link(self, link_path: Path) -> str | None:
        try:
            raw_target = os.readlink(link_path)
        except OSError:
            return None

        resolved_target = (link_path.parent / raw_target).resolve(strict=False)
        if resolved_target.parent.parent != self.objects_root:
            return None
        if not _HASH_PATTERN.match(resolved_target.name):
            return None
        return resolved_target.name

    def _sync_session_alias(self, session_id: str) -> None:
        alias_path = self.root / session_id
        target_path = Path(".sessions") / session_id

        if alias_path.is_symlink():
            current_target = Path(os.readlink(alias_path))
            if current_target == target_path:
                return
            alias_path.unlink()
        elif alias_path.exists():
            return

        alias_path.symlink_to(target_path, target_is_directory=True)

    def _remove_session_alias(self, session_id: str) -> None:
        alias_path = self.root / session_id
        if alias_path.is_symlink():
            alias_path.unlink(missing_ok=True)

    def _parse_timestamp(self, value: str | None) -> datetime:
        if not value:
            return datetime.min
        with contextlib.suppress(ValueError):
            return datetime.fromisoformat(value)
        return datetime.min

    def _normalize_ref_path(self, ref_path: Path) -> str:
        return str(ref_path.absolute())

    def _session_id_for_link_path(self, link_path: Path) -> str | None:
        with contextlib.suppress(ValueError):
            rel_path = link_path.relative_to(self.sessions_root)
            if rel_path.parts:
                return rel_path.parts[0]
        return None

    def _upsert_sqlite_object(
        self,
        *,
        content_hash: str,
        filename: str,
        size: int,
        created_at: str,
    ) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                INSERT INTO objects(content_hash, filename, size, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(content_hash) DO UPDATE SET
                    filename = COALESCE(objects.filename, excluded.filename),
                    size = excluded.size
                """,
                (content_hash, filename, size, created_at),
            )

    def _upsert_sqlite_ref(
        self,
        *,
        ref_path: Path,
        content_hash: str,
        session_id: str | None,
    ) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO refs(ref_path, content_hash, session_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self._normalize_ref_path(ref_path),
                    content_hash,
                    session_id,
                    datetime.now().isoformat(),
                ),
            )

    def _delete_sqlite_ref(self, ref_path: Path) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                "DELETE FROM refs WHERE ref_path = ?",
                (self._normalize_ref_path(ref_path),),
            )

    def _drop_sqlite_directory_refs(self, directory: Path) -> None:
        refs = [self._normalize_ref_path(link_path) for link_path, _ in self._iter_object_links(directory)]
        if not refs:
            return
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.executemany("DELETE FROM refs WHERE ref_path = ?", ((ref_path,) for ref_path in refs))

    def _delete_sqlite_object(self, content_hash: str) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute("DELETE FROM objects WHERE content_hash = ?", (content_hash,))
