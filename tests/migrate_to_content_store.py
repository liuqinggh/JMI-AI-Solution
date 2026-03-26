#!/usr/bin/env python3
"""迁移现有 uploads 到内容寻址存储"""
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


def compute_hash(file_path: Path) -> str:
    """计算文件 SHA256"""
    sha256 = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def migrate_uploads(uploads_root: Path, dry_run: bool = True):
    """迁移现有文件到内容寻址存储"""
    print(f"开始迁移: {uploads_root}")
    print(f"模式: {'dry-run' if dry_run else 'REAL'}")
    print("-" * 60)

    # 创建新目录结构
    objects_root = uploads_root / ".objects"
    sessions_root = uploads_root / ".sessions"
    metadata_root = uploads_root / ".metadata"

    if not dry_run:
        objects_root.mkdir(exist_ok=True)
        sessions_root.mkdir(exist_ok=True)
        metadata_root.mkdir(exist_ok=True)

    refs = {}
    hash_to_file = {}
    stats = {
        "total_files": 0,
        "unique_files": 0,
        "duplicates": 0,
        "total_size": 0,
        "saved_size": 0,
        "sessions_migrated": 0
    }

    # 扫描所有文件
    print("\n1. 扫描现有文件...")
    for file_path in uploads_root.rglob("*"):
        if not file_path.is_file():
            continue

        # 跳过元数据目录
        if any(part.startswith(".") for part in file_path.parts):
            continue

        stats["total_files"] += 1
        file_size = file_path.stat().st_size
        stats["total_size"] += file_size

        # 计算 hash
        content_hash = compute_hash(file_path)

        if content_hash not in hash_to_file:
            hash_to_file[content_hash] = []
            stats["unique_files"] += 1
        else:
            stats["duplicates"] += 1
            stats["saved_size"] += file_size

        hash_to_file[content_hash].append(file_path)

        # 初始化引用记录
        if content_hash not in refs:
            refs[content_hash] = {
                "filename": file_path.name,
                "size": file_size,
                "created_at": datetime.now().isoformat(),
                "ref_count": 0,
                "sessions": []
            }

    print(f"  - 总文件数: {stats['total_files']}")
    print(f"  - 唯一文件: {stats['unique_files']}")
    print(f"  - 重复文件: {stats['duplicates']}")
    print(f"  - 总大小: {stats['total_size'] / 1024 / 1024:.2f} MB")
    print(f"  - 可节省: {stats['saved_size'] / 1024 / 1024:.2f} MB")

    # 迁移文件到 objects
    print("\n2. 迁移文件到 .objects...")
    for content_hash, file_paths in hash_to_file.items():
        shard = content_hash[:2]
        shard_dir = objects_root / shard
        object_path = shard_dir / content_hash

        if not dry_run:
            shard_dir.mkdir(exist_ok=True)
            # 只保留第一个文件
            shutil.copy2(file_paths[0], object_path)

        print(f"  {content_hash[:12]}... ({len(file_paths)} copies)")

    # 重建 session 符号链接
    print("\n3. 重建 session 目录...")

    # 识别 session 目录（UUID 格式）
    session_dirs = []
    for item in uploads_root.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            # 简单判断：长度为 UUID 格式或有符号链接
            if len(item.name) == 36 or item.is_symlink():
                session_dirs.append(item)

    for session_dir in session_dirs:
        if session_dir.is_symlink():
            # 解析符号链接指向的实际目录
            actual_dir = session_dir.resolve()
            session_id = session_dir.name
        else:
            actual_dir = session_dir
            session_id = session_dir.name

        if not actual_dir.exists():
            continue

        stats["sessions_migrated"] += 1
        new_session_dir = sessions_root / session_id

        print(f"  Session: {session_id}")

        if not dry_run:
            new_session_dir.mkdir(parents=True, exist_ok=True)

        # 遍历 session 中的文件
        for file_path in actual_dir.rglob("*"):
            if not file_path.is_file():
                continue

            content_hash = compute_hash(file_path)

            if content_hash in refs:
                refs[content_hash]["ref_count"] += 1
                if session_id not in refs[content_hash]["sessions"]:
                    refs[content_hash]["sessions"].append(session_id)

                # 创建符号链接
                link_path = new_session_dir / file_path.name

                if not dry_run and not link_path.exists():
                    rel_path = Path("..") / ".." / ".objects" / content_hash[:2] / content_hash
                    link_path.symlink_to(rel_path)

                print(f"    -> {file_path.name}")

    # 保存元数据
    print("\n4. 保存元数据...")
    refs_path = metadata_root / "refs.json"

    if not dry_run:
        refs_path.write_text(
            json.dumps(refs, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    print(f"  - 引用记录: {len(refs)} 个对象")
    print(f"  - Session 数: {stats['sessions_migrated']}")

    # 清理建议
    print("\n5. 清理建议:")
    print("  迁移完成后，可以删除以下目录:")
    old_dirs = [d for d in uploads_root.iterdir()
                if d.is_dir() and not d.name.startswith(".")]
    for old_dir in old_dirs:
        print(f"    - {old_dir.name}")

    print("\n" + "=" * 60)
    print("迁移统计:")
    print(f"  总文件数: {stats['total_files']}")
    print(f"  唯一文件: {stats['unique_files']}")
    print(f"  去重率: {(stats['duplicates'] / stats['total_files'] * 100) if stats['total_files'] > 0 else 0:.1f}%")
    print(f"  节省空间: {stats['saved_size'] / 1024 / 1024:.2f} MB")
    print(f"  Session 数: {stats['sessions_migrated']}")
    print("=" * 60)

    if dry_run:
        print("\n⚠️  这是 dry-run 模式，未做任何修改")
        print("   使用 --real 参数执行实际迁移")


if __name__ == "__main__":
    import sys

    uploads_root = Path(__file__).parent.parent / "uploads"
    dry_run = "--real" not in sys.argv

    if not uploads_root.exists():
        print(f"错误: uploads 目录不存在: {uploads_root}")
        sys.exit(1)

    migrate_uploads(uploads_root, dry_run=dry_run)
