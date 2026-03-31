"""Health check and configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.deps import ConfigDep
from app.schemas import ConfigInfo, HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns service status and version information.
    No authentication required.
    """
    return HealthResponse(
        status="healthy",
        service="agent-sdk-api-service",
        version="0.1.0",
    )


@router.get("/config", response_model=ConfigInfo)
async def get_config_info(config: ConfigDep) -> ConfigInfo:
    """Get current configuration information.

    Returns runtime configuration including model, provider,
    and various SDK settings.

    Args:
        config: Application configuration (injected)

    Returns:
        Configuration information
    """
    use_vertex = config.sdk.env.get("CLAUDE_CODE_USE_VERTEX") == "1"
    use_bedrock = config.sdk.env.get("CLAUDE_CODE_USE_BEDROCK") == "1"
    use_foundry = config.sdk.env.get("CLAUDE_CODE_USE_FOUNDRY") == "1"

    provider = "Local Proxy"
    if use_vertex:
        provider = "Vertex AI"
    elif use_bedrock:
        provider = "AWS Bedrock"
    elif use_foundry:
        provider = "Anthropic Foundry"

    return ConfigInfo(
        model=config.sdk.model,
        provider=provider,
        max_turns=config.sdk.max_turns,
        permission_mode=config.sdk.permission_mode or "manual",
        vertex_project_id=config.sdk.env.get("ANTHROPIC_VERTEX_PROJECT_ID") if use_vertex else None,
        region=config.sdk.env.get("CLOUD_ML_REGION") if use_vertex else None,
    )
