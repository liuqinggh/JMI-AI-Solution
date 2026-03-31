from __future__ import annotations

from fastapi import FastAPI

from app.api import api_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(
        title=resolved_settings.app.name,
        version=resolved_settings.app.version,
    )
    app.include_router(api_router)
    return app


app = create_app()
