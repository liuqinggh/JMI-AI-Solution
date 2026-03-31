from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.core.session_id import validate_business_session_id


class ChatRequest(BaseModel):
    message: str
    business_session_id: str
    app_id: str | None = None
    skill_name: str | None = None
    file_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_target(self) -> ChatRequest:
        validate_business_session_id(self.business_session_id)
        if not self.app_id and not self.skill_name:
            raise ValueError("Either app_id or skill_name must be provided")
        return self
