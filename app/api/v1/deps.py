"""Dependencies for v1 API endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.config import AppConfig, get_config
from app.storage.content_store import ContentAddressedStore
from app.tracing.langfuse_tracer import LangfuseTracer

# Shared instances (initialized at app startup)
_config: AppConfig | None = None
_file_store: ContentAddressedStore | None = None
_tracer: LangfuseTracer | None = None


def init_dependencies(
    config: AppConfig,
    file_store: ContentAddressedStore,
    tracer: LangfuseTracer,
) -> None:
    """Initialize shared dependencies at app startup.

    Args:
        config: Application configuration
        file_store: Content-addressed file storage
        tracer: Langfuse tracer instance
    """
    global _config, _file_store, _tracer
    _config = config
    _file_store = file_store
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


def get_file_store() -> ContentAddressedStore:
    """Get file storage instance.

    Returns:
        Content-addressed file storage

    Raises:
        RuntimeError: If dependencies not initialized
    """
    if _file_store is None:
        raise RuntimeError("Dependencies not initialized. Call init_dependencies() first.")
    return _file_store


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
FileStoreDep = Annotated[ContentAddressedStore, Depends(get_file_store)]
TracerDep = Annotated[LangfuseTracer, Depends(get_langfuse_tracer)]
