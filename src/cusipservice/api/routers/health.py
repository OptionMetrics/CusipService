"""Health check endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

import psycopg2
from fastapi import APIRouter, Depends

from cusipservice.api.dependencies import get_db_config
from cusipservice.api.models import HealthResponse
from cusipservice.loader import DbConfig

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    db_config: Annotated[DbConfig, Depends(get_db_config)],
) -> HealthResponse:
    """
    Health check endpoint.

    Returns database connectivity status.
    No authentication required.
    """
    db_status: Literal["connected", "disconnected"]
    try:
        conn = psycopg2.connect(**db_config)
        conn.close()
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        database=db_status,
        version="0.1.0",
    )


@router.get("/ready")
def readiness_check(
    db_config: Annotated[DbConfig, Depends(get_db_config)],
) -> dict[str, str]:
    """
    Kubernetes readiness probe.

    Returns 200 only if database is accessible.
    """
    try:
        conn = psycopg2.connect(**db_config)
        conn.close()
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not ready", "reason": str(e)}


@router.get("/live")
def liveness_check() -> dict[str, str]:
    """
    Kubernetes liveness probe.

    Always returns 200 if the application is running.
    """
    return {"status": "alive"}
