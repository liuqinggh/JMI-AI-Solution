from __future__ import annotations

from pathlib import Path

from app.core.session_id import validate_business_session_id
from app.models.session import SessionMapping, utc_now


class SessionManager:
    def __init__(self, storage_dir: str | Path):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, business_session_id: str) -> Path:
        safe_session_id = validate_business_session_id(business_session_id)
        return self.storage_dir / f"{safe_session_id}.json"

    def save_mapping(
        self,
        *,
        business_session_id: str,
        sdk_session_id: str,
        app_id: str | None,
        skill_name: str,
    ) -> SessionMapping:
        current = self.get_mapping(business_session_id)
        created_at = current.created_at if current else utc_now()
        mapping = SessionMapping(
            business_session_id=business_session_id,
            sdk_session_id=sdk_session_id,
            app_id=app_id,
            skill_name=skill_name,
            created_at=created_at,
            updated_at=utc_now(),
        )
        self._path_for(business_session_id).write_text(
            mapping.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return mapping

    def get_mapping(self, business_session_id: str) -> SessionMapping | None:
        path = self._path_for(business_session_id)
        if not path.exists():
            return None
        return SessionMapping.model_validate_json(path.read_text(encoding="utf-8"))
