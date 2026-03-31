"""FastAPI application entry point."""

from __future__ import annotations

import uvicorn

from app.api.app import create_app
from app.config import configure_sdk_environment, get_config
from app.core.logging import setup_logging

# Initialize logging
setup_logging(level="INFO", use_colors=True)

# Load configuration and create app
config = configure_sdk_environment(get_config())
app = create_app(config)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=config.app.host,
        port=config.app.port,
        reload=config.app.reload,
    )
