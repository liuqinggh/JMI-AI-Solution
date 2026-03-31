from __future__ import annotations

from fastapi import HTTPException

from app.core.config import Settings
from app.models.app import RegisteredApp


class AppRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings

    def get_app(self, app_id: str) -> RegisteredApp:
        definition = self.settings.apps.get(app_id)
        if definition is None:
            raise HTTPException(status_code=404, detail=f"App '{app_id}' not found")
        return RegisteredApp(
            app_id=app_id,
            skill_name=definition.skill_name,
            cwd=definition.cwd,
            permission_mode=definition.permission_mode,
            allowed_tools=list(definition.allowed_tools),
        )
