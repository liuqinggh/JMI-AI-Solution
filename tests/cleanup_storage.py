#!/usr/bin/env python3
"""存储清理工具"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config
from src.storage.content_store import ContentAddressedStore


def main():
    import argparse

    parser = argparse.ArgumentParser(description="清理存储中的孤立文件")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="清理多少天前的孤立文件（默认: 7）"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="只显示统计信息"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行，不实际删除"
    )

    args = parser.parse_args()

    # 初始化存储
    config = get_config()
    store = ContentAddressedStore(config.storage)

    print("=" * 60)
    print("存储状态")
    print("=" * 60)

    # 显示统计
    stats = store.get_stats()
    print(f"总对象数: {stats['total_objects']}")
    print(f"总大小: {stats['total_size_mb']} MB")
    print(f"总引用数: {stats['total_references']}")
    print(f"孤立对象: {stats['orphaned_objects']}")
    print(f"Session 数: {stats['sessions']}")
    print(f"去重率: {stats['dedup_ratio']}x")

    if args.stats:
        return

    print("\n" + "=" * 60)
    print(f"清理操作 (保留 {args.days} 天内的文件)")
    print("=" * 60)

    if args.dry_run:
        print("⚠️  DRY-RUN 模式，不会实际删除文件\n")

    # 执行清理
    if not args.dry_run:
        orphaned_count = store.cleanup_orphans(days=args.days)
        print(f"✓ 已清理 {orphaned_count} 个孤立对象")

        # 显示清理后的统计
        stats = store.get_stats()
        print(f"\n清理后:")
        print(f"  总对象数: {stats['total_objects']}")
        print(f"  总大小: {stats['total_size_mb']} MB")
        print(f"  孤立对象: {stats['orphaned_objects']}")
    else:
        print("执行以下命令进行实际清理:")
        print(f"  python scripts/cleanup_storage.py --days {args.days}")


if __name__ == "__main__":
    main()
