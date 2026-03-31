"""Health check and system information schemas."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response.

    Returned by the health endpoint to indicate service status.
    """

    status: str
    service: str
    version: str


class ConfigInfo(BaseModel):
    """Current configuration information.

    Contains runtime configuration details such as model,
    provider, and various SDK settings.
    """

    model: str
    provider: str
    max_turns: int
    permission_mode: str
    vertex_project_id: str | None = None
    region: str | None = None
