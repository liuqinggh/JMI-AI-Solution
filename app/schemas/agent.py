"""Agent request and response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentStep(BaseModel):
    """Single step in agent execution trace."""

    type: str
    content: str


class AgentResponse(BaseModel):
    """Standard agent execution response.

    Returned when agent completes a task, contains final answer,
    execution steps, and optional structured output.
    """

    session_id: str
    final_answer: str
    steps: list[AgentStep] = Field(default_factory=list)
    success: bool = True
    final_answer_text_policy: str = "full"
    structured_output: dict[str, Any] | None = None
    structured_valid: bool | None = None
    structured_error: str | None = None


class ExecutionResult(BaseModel):
    """Internal execution result from agent executor.

    This is used internally between executor and API routes,
    and is converted to AgentResponse for external responses.
    """

    session_id: str
    final_answer: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    success: bool = True
    final_answer_text_policy: str = "full"
    structured_output: dict[str, Any] | None = None
