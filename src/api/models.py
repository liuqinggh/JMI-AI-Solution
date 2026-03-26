from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentStep(BaseModel):
    type: str
    content: str


class AgentResponse(BaseModel):
    session_id: str
    final_answer: str
    steps: list[AgentStep] = Field(default_factory=list)
    success: bool = True
    final_answer_text_policy: str = "full"
    structured_output: dict[str, Any] | None = None
    structured_valid: bool | None = None
    structured_error: str | None = None


class StructuredAgentResponse(BaseModel):
    """structured_output_profile 校验成功时的精简响应：只含 session_id 和结果。"""

    session_id: str
    structured_output: dict[str, Any]


class ExecutionResult(BaseModel):
    session_id: str
    final_answer: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    success: bool = True
    final_answer_text_policy: str = "full"
    structured_output: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ConfigInfo(BaseModel):
    model: str
    provider: str
    max_turns: int
    permission_mode: str
    vertex_project_id: str | None = None
    region: str | None = None
