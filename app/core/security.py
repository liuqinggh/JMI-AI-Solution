"""Security utilities for API authentication."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, APIKeyQuery

# API Key can be provided via header or query parameter
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def get_api_key_from_env() -> str | None:
    """Get the expected API key from environment variables.

    Returns:
        The API key from AGENT_API_KEY environment variable, or None if not set.
    """
    return os.environ.get("AGENT_API_KEY")


async def verify_api_key(
    header_key: str | None = Security(api_key_header),
    query_key: str | None = Security(api_key_query),
) -> str:
    """Verify API key from header or query parameter.

    This dependency can be used to protect endpoints that require authentication.

    Args:
        header_key: API key from X-API-Key header
        query_key: API key from api_key query parameter

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is missing or invalid (401 Unauthorized)

    Example:
        @app.get("/protected")
        async def protected_endpoint(api_key: str = Depends(verify_api_key)):
            return {"message": "Access granted"}
    """
    expected_key = get_api_key_from_env()

    # If no API key is configured, authentication is disabled
    if not expected_key:
        return "authentication_disabled"

    # Check header first, then query parameter
    provided_key = header_key or query_key

    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required. Provide via X-API-Key header or api_key query parameter.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if provided_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return provided_key


async def get_optional_api_key(
    header_key: str | None = Security(api_key_header),
    query_key: str | None = Security(api_key_query),
) -> str | None:
    """Get API key without enforcing authentication.

    This is useful for endpoints that have optional authentication,
    or when authentication is only enforced in production.

    Args:
        header_key: API key from X-API-Key header
        query_key: API key from api_key query parameter

    Returns:
        The API key if provided, None otherwise
    """
    return header_key or query_key


# Type alias for dependency injection
APIKeyDep = Annotated[str, Depends(verify_api_key)]
OptionalAPIKeyDep = Annotated[str | None, Depends(get_optional_api_key)]
