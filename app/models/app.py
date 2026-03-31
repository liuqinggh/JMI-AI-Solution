from __future__ import annotations

from pydantic import BaseModel, Field


class RegisteredApp(BaseModel):
    app_id: str
    skill_name: str
    cwd: str
    permission_mode: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
