"""Backward compatibility entry point.

For new code, use: python -m uvicorn app.main:app
"""

from app.main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    from app.config import get_config

    config = get_config()
    uvicorn.run(
        "app.main:app",
        host=config.app.host,
        port=config.app.port,
        reload=config.app.reload,
    )
