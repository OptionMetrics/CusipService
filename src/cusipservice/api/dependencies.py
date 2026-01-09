"""FastAPI dependencies for authentication and configuration."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cusipservice.config import Settings, get_settings
from cusipservice.loader import DbConfig

security = HTTPBearer()


def get_db_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DbConfig:
    """Get database configuration as typed dict."""
    return {
        "host": settings.db_host,
        "port": settings.db_port,
        "dbname": settings.db_name,
        "user": settings.db_user,
        "password": settings.db_password,
    }


def verify_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Verify bearer token and return the token if valid."""
    if not settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API token not configured",
        )

    if credentials.credentials != settings.api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
