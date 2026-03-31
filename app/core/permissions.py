from __future__ import annotations

from app.core.config import AppDefinition, Settings
from app.models.app import RegisteredApp
from app.models.session import PermissionProfile


def resolve_permissions(
    *,
    settings: Settings,
    app_definition: AppDefinition | RegisteredApp,
) -> PermissionProfile:
    permission_mode = app_definition.permission_mode or settings.claude.permission_mode
    allowed_tools = app_definition.allowed_tools or settings.claude.default_allowed_tools
    return PermissionProfile(permission_mode=permission_mode, allowed_tools=allowed_tools)
