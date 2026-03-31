"""Structured output schemas for specialized responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StructuredAgentResponse(BaseModel):
    """Simplified response for structured output profiles.

    When structured_output_profile is enabled and validation succeeds,
    this minimal response is returned containing only the session_id
    and the validated structured output.

    This is useful for API clients that only need the structured data
    without execution steps or intermediate analysis.
    """

    session_id: str
    structured_output: dict[str, Any]
