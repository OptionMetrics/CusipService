"""
File discovery utilities for CUSIP PIF files.

This module provides backwards-compatible imports from file_source.py
and utility functions for date parsing.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import NamedTuple

# Re-export FileSet and related classes from file_source for backwards compatibility
from cusipservice.file_source import (
    FileInfo,
    FileSet,
    LocalFileSource,
    S3FileSource,
    create_file_source,
)

__all__ = [
    "FileInfo",
    "FileSet",
    "LocalFileSource",
    "S3FileSource",
    "create_file_source",
    "find_files_for_date",
    "parse_date_param",
    "LegacyFileSet",
]


class LegacyFileSet(NamedTuple):
    """
    Legacy file set for backwards compatibility.

    Deprecated: Use FileSet from file_source instead.
    """

    issuer: Path | None
    issue: Path | None
    issue_attr: Path | None
    target_date: date


def find_files_for_date(
    directory: Path,
    target_date: date | None = None,
) -> LegacyFileSet:
    """
    Find CUSIP PIF files for a specific date (legacy function).

    This function is maintained for backwards compatibility.
    For new code, use LocalFileSource or S3FileSource directly.

    Args:
        directory: Directory containing PIF files
        target_date: Date to search for (defaults to today)

    Returns:
        LegacyFileSet with paths to issuer, issue, and issue_attr files

    Raises:
        FileNotFoundError: If directory doesn't exist
    """
    source = LocalFileSource(directory)
    file_set = source.find_files_for_date(target_date)

    return LegacyFileSet(
        issuer=file_set.issuer.local_path if file_set.issuer else None,
        issue=file_set.issue.local_path if file_set.issue else None,
        issue_attr=file_set.issue_attr.local_path if file_set.issue_attr else None,
        target_date=file_set.target_date,
    )


def parse_date_param(date_str: str | None) -> date:
    """
    Parse date parameter from API request.

    Args:
        date_str: Date string in YYYY-MM-DD format or None

    Returns:
        Parsed date or today's date if None

    Raises:
        ValueError: If date_str is not in valid format
    """
    if date_str is None:
        return date.today()

    # Validate format YYYY-MM-DD
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD")

    return date.fromisoformat(date_str)
