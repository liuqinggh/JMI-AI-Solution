import uvicorn

from src.config import configure_sdk_environment, get_config
from src.api.routes import app


config = configure_sdk_environment(get_config())


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.app.host,
        port=config.app.port,
        reload=config.app.reload,
    )
