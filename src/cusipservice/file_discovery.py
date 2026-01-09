"""File discovery utilities for CUSIP PIF files."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import NamedTuple


class FileSet(NamedTuple):
    """Set of CUSIP files for a given date."""

    issuer: Path | None
    issue: Path | None
    issue_attr: Path | None
    target_date: date


def find_files_for_date(
    directory: Path,
    target_date: date | None = None,
) -> FileSet:
    """
    Find CUSIP PIF files for a specific date.

    Args:
        directory: Directory containing PIF files
        target_date: Date to search for (defaults to today)

    Returns:
        FileSet with paths to issuer, issue, and issue_attr files

    Raises:
        FileNotFoundError: If directory doesn't exist
    """
    if target_date is None:
        target_date = date.today()

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Pattern: CMD followed by mm-dd (e.g., CMD01-15)
    date_pattern = target_date.strftime("%m-%d")
    pattern = f"CMD{date_pattern}*"

    issuer_file: Path | None = None
    issue_file: Path | None = None
    issue_attr_file: Path | None = None

    for filepath in directory.glob(pattern + ".PIP"):
        name_upper = filepath.name.upper()
        if name_upper.endswith("R.PIP"):
            issuer_file = filepath
        elif name_upper.endswith("E.PIP"):
            issue_file = filepath
        elif name_upper.endswith("A.PIP"):
            issue_attr_file = filepath

    return FileSet(
        issuer=issuer_file,
        issue=issue_file,
        issue_attr=issue_attr_file,
        target_date=target_date,
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
