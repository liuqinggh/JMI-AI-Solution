from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class SessionMapping(BaseModel):
    business_session_id: str
    sdk_session_id: str
    app_id: str | None = None
    skill_name: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PermissionProfile(BaseModel):
    permission_mode: str
    allowed_tools: list[str]
