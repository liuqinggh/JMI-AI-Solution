from __future__ import annotations

import sqlite3
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile

from src.config import StorageSettings
from src.storage.content_store import ContentAddressedStore


def _upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


async def test_content_store_deduplicates_files_across_sessions(tmp_path):
    store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    session_a = store.ensure_session_dir("session-a")
    session_b = store.ensure_session_dir("session-b")

    saved_a = await store.save_uploads([_upload("report.txt", b"same-content")], session_a)
    saved_b = await store.save_uploads([_upload("copy.txt", b"same-content")], session_b)

    link_a = session_a / saved_a[0]
    link_b = session_b / saved_b[0]

    assert link_a.is_symlink()
    assert link_b.is_symlink()
    assert link_a.resolve() == link_b.resolve()

    stats = store.get_stats()
    assert stats["total_objects"] == 1
    assert stats["total_references"] == 2
    assert stats["sessions"] == 2

    store.cleanup_session("session-a")
    stats = store.get_stats()
    assert stats["total_objects"] == 1
    assert stats["total_references"] == 1
    assert stats["sessions"] == 1

    store.cleanup_session("session-b")
    stats = store.get_stats()
    assert stats["total_objects"] == 0
    assert stats["total_references"] == 0


async def test_same_session_same_filename_same_content_reuses_existing_link(tmp_path):
    store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    session_dir = store.ensure_session_dir("session-a")

    first_saved = await store.save_uploads([_upload("report.txt", b"same-content")], session_dir)
    second_saved = await store.save_uploads([_upload("report.txt", b"same-content")], session_dir)

    assert first_saved == ["report.txt"]
    assert second_saved == ["report.txt"]
    assert [item.name for item in session_dir.iterdir()] == ["report.txt"]

    stats = store.get_stats()
    assert stats["total_objects"] == 1
    assert stats["total_references"] == 1


async def test_finalize_pending_dir_promotes_workspace_into_session_dir(tmp_path):
    store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    pending_dir = store.create_pending_dir()
    saved_names = await store.save_uploads([_upload("report.pdf", b"demo")], pending_dir)

    session_dir = store.finalize_pending_dir(pending_dir, "session-1")
    saved_file = session_dir / saved_names[0]

    assert session_dir == tmp_path / "uploads" / ".sessions" / "session-1"
    assert saved_file.exists()
    assert saved_file.is_symlink()
    assert not pending_dir.exists()
    assert (tmp_path / "uploads" / "session-1").is_symlink()

    stats = store.get_stats()
    assert stats["total_objects"] == 1
    assert stats["total_references"] == 1


def _fetch_one(db_path: Path, sql: str, params: tuple = ()) -> tuple | None:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(sql, params).fetchone()


async def test_content_store_persists_dedup_metadata_in_sqlite(tmp_path):
    store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    session_a = store.ensure_session_dir("session-a")
    session_b = store.ensure_session_dir("session-b")

    await store.save_uploads([_upload("report.txt", b"same-content")], session_a)
    await store.save_uploads([_upload("copy.txt", b"same-content")], session_b)

    db_path = tmp_path / "uploads" / ".metadata" / "storage.db"
    assert db_path.exists()

    object_row = _fetch_one(
        db_path,
        "SELECT COUNT(*) FROM objects",
    )
    ref_row = _fetch_one(
        db_path,
        "SELECT COUNT(*) FROM refs",
    )
    sessions = _fetch_one(
        db_path,
        "SELECT GROUP_CONCAT(DISTINCT session_id) FROM refs WHERE session_id IS NOT NULL",
    )

    assert object_row == (1,)
    assert ref_row == (2,)
    assert sessions is not None
    assert sessions[0] is not None
    assert "session-a" in sessions[0]
    assert "session-b" in sessions[0]


async def test_finalize_pending_dir_rewrites_pending_refs_to_session_refs_in_sqlite(tmp_path):
    store = ContentAddressedStore(
        StorageSettings(upload_root=str(tmp_path / "uploads"), pending_dir_name=".pending")
    )

    pending_dir = store.create_pending_dir()
    saved_names = await store.save_uploads([_upload("report.pdf", b"demo")], pending_dir)

    db_path = tmp_path / "uploads" / ".metadata" / "storage.db"
    pending_ref = _fetch_one(
        db_path,
        "SELECT ref_path, session_id FROM refs WHERE ref_path LIKE ?",
        (f"%{saved_names[0]}",),
    )
    assert pending_ref is not None
    assert pending_ref[1] is None
    assert ".pending" in pending_ref[0]

    session_dir = store.finalize_pending_dir(pending_dir, "session-1")

    pending_ref_after = _fetch_one(
        db_path,
        "SELECT ref_path FROM refs WHERE ref_path = ?",
        (pending_ref[0],),
    )
    session_ref = _fetch_one(
        db_path,
        "SELECT ref_path, session_id FROM refs WHERE ref_path = ?",
        (str(session_dir / saved_names[0]),),
    )

    assert pending_ref_after is None
    assert session_ref == (str(session_dir / saved_names[0]), "session-1")
