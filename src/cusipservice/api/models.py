"""Pydantic models for API requests and responses."""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job execution status."""

    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class LoadRequest(BaseModel):
    """Request model for file load endpoints."""

    date: Optional[datetime.date] = Field(
        default=None,
        description="Date for file discovery (YYYY-MM-DD). Defaults to today.",
        examples=["2024-01-15"],
    )


class FileLoadResult(BaseModel):
    """Result of loading a single file."""

    file: str = Field(description="File path that was loaded")
    type: Literal["issuer", "issue", "issue_attr"]
    rows_read: int = Field(ge=0)
    rows_upserted: int = Field(ge=0)
    status: JobStatus
    error: Optional[str] = Field(default=None)


class LoadResponse(BaseModel):
    """Response model for file load endpoints."""

    success: bool
    message: str
    results: list[FileLoadResult] = Field(default_factory=list)
    date: datetime.date


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "unhealthy"]
    database: Literal["connected", "disconnected"]
    version: str
