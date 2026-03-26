from __future__ import annotations

from src.storage.content_store import ContentAddressedStore


class FileStore(ContentAddressedStore):
    """兼容旧导入路径，实际实现已切换为内容寻址存储。"""

