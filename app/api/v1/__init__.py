"""API version 1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import agents, health, test

# Create v1 API router
api_router = APIRouter(prefix="/v1")

# Include all endpoint routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(test.router, tags=["test"])
api_router.include_router(agents.router, tags=["agents"])

__all__ = ["api_router"]
