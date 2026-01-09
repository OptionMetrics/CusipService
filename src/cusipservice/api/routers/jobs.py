"""Job endpoints for loading CUSIP files."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from cusipservice.api.dependencies import get_db_config, verify_token
from cusipservice.api.models import (
    FileLoadResult,
    JobStatus,
    LoadRequest,
    LoadResponse,
)
from cusipservice.config import Settings, get_settings
from cusipservice.file_source import (
    FileInfo,
    FileSet,
    LocalFileSource,
    S3FileSource,
    create_file_source,
)
from cusipservice.loader import DbConfig, load_from_source

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(verify_token)],
)


def _get_file_source(settings: Settings) -> LocalFileSource | S3FileSource:
    """Create file source from settings."""
    return create_file_source(
        source_type=settings.file_source,
        file_dir=settings.file_dir,
        s3_bucket=settings.s3_bucket,
        s3_prefix=settings.s3_prefix,
        s3_region=settings.s3_region if settings.s3_region else None,
    )


def _load_single_file(
    file_type: str,
    files: FileSet,
    db_config: DbConfig,
    file_source: LocalFileSource | S3FileSource,
) -> FileLoadResult:
    """Load a single file type from the file set."""
    file_map: dict[str, FileInfo | None] = {
        "issuer": files.issuer,
        "issue": files.issue,
        "issue_attr": files.issue_attr,
    }

    file_info = file_map.get(file_type)
    if file_info is None:
        return FileLoadResult(
            file="",
            type=file_type,  # type: ignore[arg-type]
            rows_read=0,
            rows_upserted=0,
            status=JobStatus.SKIPPED,
            error=f"No {file_type} file found for date {files.target_date}",
        )

    result = load_from_source(file_info, file_type, db_config, file_source)

    return FileLoadResult(
        file=result.get("file", ""),
        type=result.get("type", file_type),  # type: ignore[arg-type]
        rows_read=result.get("rows_read", 0),
        rows_upserted=result.get("rows_upserted", 0),
        status=JobStatus(result.get("status", "error")),
        error=result.get("error"),
    )


@router.post("/load-issuer", response_model=LoadResponse)
def load_issuer(
    request: LoadRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_config: Annotated[DbConfig, Depends(get_db_config)],
) -> LoadResponse:
    """Load issuer file (R.PIP) for the specified date."""
    target_date = request.date or date.today()

    try:
        file_source = _get_file_source(settings)
        files = file_source.find_files_for_date(target_date)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    result = _load_single_file("issuer", files, db_config, file_source)
    success = result.status == JobStatus.SUCCESS

    return LoadResponse(
        success=success,
        message=f"Issuer load {'completed' if success else 'failed'}",
        results=[result],
        date=target_date,
    )


@router.post("/load-issue", response_model=LoadResponse)
def load_issue(
    request: LoadRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_config: Annotated[DbConfig, Depends(get_db_config)],
) -> LoadResponse:
    """Load issue file (E.PIP) for the specified date."""
    target_date = request.date or date.today()

    try:
        file_source = _get_file_source(settings)
        files = file_source.find_files_for_date(target_date)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    result = _load_single_file("issue", files, db_config, file_source)
    success = result.status == JobStatus.SUCCESS

    return LoadResponse(
        success=success,
        message=f"Issue load {'completed' if success else 'failed'}",
        results=[result],
        date=target_date,
    )


@router.post("/load-issue-attr", response_model=LoadResponse)
def load_issue_attr(
    request: LoadRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_config: Annotated[DbConfig, Depends(get_db_config)],
) -> LoadResponse:
    """Load issue attributes file (A.PIP) for the specified date."""
    target_date = request.date or date.today()

    try:
        file_source = _get_file_source(settings)
        files = file_source.find_files_for_date(target_date)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    result = _load_single_file("issue_attr", files, db_config, file_source)
    success = result.status == JobStatus.SUCCESS

    return LoadResponse(
        success=success,
        message=f"Issue attributes load {'completed' if success else 'failed'}",
        results=[result],
        date=target_date,
    )


@router.post("/load-all", response_model=LoadResponse)
def load_all(
    request: LoadRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_config: Annotated[DbConfig, Depends(get_db_config)],
) -> LoadResponse:
    """
    Load all files in correct order: issuer -> issue -> issue_attr.

    Due to foreign key constraints, files must be loaded in this order.
    If any load fails, subsequent loads are skipped.
    """
    target_date = request.date or date.today()

    try:
        file_source = _get_file_source(settings)
        files = file_source.find_files_for_date(target_date)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    results: list[FileLoadResult] = []
    load_order = ["issuer", "issue", "issue_attr"]

    for file_type in load_order:
        result = _load_single_file(file_type, files, db_config, file_source)
        results.append(result)

        # Stop if a load fails (not just skipped)
        if result.status == JobStatus.ERROR:
            break

    all_success = all(
        r.status in (JobStatus.SUCCESS, JobStatus.SKIPPED) for r in results
    )
    has_error = any(r.status == JobStatus.ERROR for r in results)

    if has_error:
        message = "Load failed - check results for details"
    elif all_success:
        message = "All files loaded successfully"
    else:
        message = "Load completed with warnings"

    return LoadResponse(
        success=all_success and not has_error,
        message=message,
        results=results,
        date=target_date,
    )
