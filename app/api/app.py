"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.v1 import api_router
from app.api.v1.deps import init_dependencies
from app.config import AppConfig, configure_sdk_environment, get_config
from app.storage.content_store import ContentAddressedStore
from app.tracing.langfuse_tracer import LangfuseTracer


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create and configure FastAPI application.

    Args:
        config: Application configuration. If None, loads from default config file.

    Returns:
        Configured FastAPI application instance
    """
    # Load and configure environment
    if config is None:
        config = configure_sdk_environment(get_config())

    # Initialize storage and tracing
    file_store = ContentAddressedStore(config.storage)
    tracer = LangfuseTracer(config.langfuse)

    # Initialize dependencies for v1 API
    init_dependencies(config, file_store, tracer)

    # Set global tracer for executor
    from app.agents.executor import set_tracer

    set_tracer(tracer)

    # Create FastAPI app
    app = FastAPI(
        title="Agent SDK API Service",
        version="0.1.0",
        description="FastAPI wrapper around Claude Agent SDK with MCP tool support",
    )

    # Register shutdown handler
    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        """Cleanup on shutdown."""
        tracer.shutdown()

    # Include API router with /api prefix
    app.include_router(api_router, prefix="/api")

    # Root redirect or health check
    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint - redirect to API documentation."""
        return {
            "message": "Agent SDK API Service",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app
