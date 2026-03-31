"""Dependencies for v1 API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.config import AppConfig, get_config
from app.services.session_workspace_service import SessionWorkspaceService
from app.services.upload_batch_service import UploadBatchService
from app.tracing.langfuse_tracer import LangfuseTracer

# Shared instances (initialized at app startup)
_config: AppConfig | None = None
_batch_service: UploadBatchService | None = None
_workspace_service: SessionWorkspaceService | None = None
_tracer: LangfuseTracer | None = None


def init_dependencies(
    config: AppConfig,
    batch_service: UploadBatchService,
    workspace_service: SessionWorkspaceService,
    tracer: LangfuseTracer,
) -> None:
    """Initialize shared dependencies at app startup.

    Args:
        config: Application configuration
        batch_service: Upload batch service
        workspace_service: Session workspace service
        tracer: Langfuse tracer instance
    """
    global _config, _batch_service, _workspace_service, _tracer
    _config = config
    _batch_service = batch_service
    _workspace_service = workspace_service
    _tracer = tracer


def get_app_config() -> AppConfig:
    """Get application configuration.

    Returns:
        Application configuration instance

    Raises:
        RuntimeError: If dependencies not initialized
    """
    if _config is None:
        raise RuntimeError("Dependencies not initialized. Call init_dependencies() first.")
    return _config


def get_batch_service() -> UploadBatchService:
    """Get upload batch service.

    Returns:
        Upload batch service

    Raises:
        RuntimeError: If dependencies not initialized
    """
    if _batch_service is None:
        raise RuntimeError("Dependencies not initialized. Call init_dependencies() first.")
    return _batch_service


def get_workspace_service() -> SessionWorkspaceService:
    """Get session workspace service.

    Returns:
        Session workspace service

    Raises:
        RuntimeError: If dependencies not initialized
    """
    if _workspace_service is None:
        raise RuntimeError("Dependencies not initialized. Call init_dependencies() first.")
    return _workspace_service


def get_langfuse_tracer() -> LangfuseTracer:
    """Get Langfuse tracer instance.

    Returns:
        Langfuse tracer

    Raises:
        RuntimeError: If dependencies not initialized
    """
    if _tracer is None:
        raise RuntimeError("Dependencies not initialized. Call init_dependencies() first.")
    return _tracer


# Type aliases for dependency injection
ConfigDep = Annotated[AppConfig, Depends(get_app_config)]
BatchServiceDep = Annotated[UploadBatchService, Depends(get_batch_service)]
WorkspaceServiceDep = Annotated[SessionWorkspaceService, Depends(get_workspace_service)]
TracerDep = Annotated[LangfuseTracer, Depends(get_langfuse_tracer)]
