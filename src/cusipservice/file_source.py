"""
File source abstraction for local filesystem and S3.

This module provides a unified interface for discovering and reading CUSIP PIP files
from either a local directory or an S3 bucket. It supports AWS SSO profiles via
the standard AWS_PROFILE environment variable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


@dataclass
class FileInfo:
    """Information about a discovered file."""

    name: str
    source: str  # 'local' or 's3'
    local_path: Path | None = None  # Set for local files
    s3_bucket: str | None = None  # Set for S3 files
    s3_key: str | None = None  # Set for S3 files

    @property
    def display_path(self) -> str:
        """Return a display-friendly path for logging."""
        if self.source == "local" and self.local_path:
            return str(self.local_path)
        elif self.source == "s3" and self.s3_bucket and self.s3_key:
            return f"s3://{self.s3_bucket}/{self.s3_key}"
        return self.name


@dataclass
class FileSet:
    """Set of CUSIP files for a given date."""

    issuer: FileInfo | None
    issue: FileInfo | None
    issue_attr: FileInfo | None
    target_date: date


class FileSource(Protocol):
    """Protocol for file source implementations."""

    def find_files_for_date(self, target_date: date | None = None) -> FileSet:
        """Find CUSIP PIP files for a specific date."""
        ...

    def read_file(self, file_info: FileInfo) -> list[str]:
        """Read file contents as a list of lines."""
        ...


class LocalFileSource:
    """File source for local filesystem."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def find_files_for_date(self, target_date: date | None = None) -> FileSet:
        """Find CUSIP PIP files in local directory for a specific date."""
        if target_date is None:
            target_date = date.today()

        if not self.directory.exists():
            raise FileNotFoundError(f"Directory not found: {self.directory}")

        date_pattern = target_date.strftime("%m-%d")
        pattern = f"CED{date_pattern}*.PIP"

        issuer_file: FileInfo | None = None
        issue_file: FileInfo | None = None
        issue_attr_file: FileInfo | None = None

        for filepath in self.directory.glob(pattern):
            name_upper = filepath.name.upper()
            file_info = FileInfo(
                name=filepath.name,
                source="local",
                local_path=filepath,
            )
            if name_upper.endswith("R.PIP"):
                issuer_file = file_info
            elif name_upper.endswith("E.PIP"):
                issue_file = file_info
            elif name_upper.endswith("A.PIP"):
                issue_attr_file = file_info

        return FileSet(
            issuer=issuer_file,
            issue=issue_file,
            issue_attr=issue_attr_file,
            target_date=target_date,
        )

    def read_file(self, file_info: FileInfo) -> list[str]:
        """Read file contents from local filesystem."""
        if file_info.local_path is None:
            raise ValueError(f"No local path for file: {file_info.name}")

        with open(file_info.local_path, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()


class S3FileSource:
    """
    File source for S3 bucket.

    Supports AWS credentials via:
    - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    - AWS SSO profiles (AWS_PROFILE environment variable)
    - IAM roles (when running on AWS infrastructure)
    - Default credential chain
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "pip/",
        region: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        self.region = region
        self._client: S3Client | None = None

    @property
    def client(self) -> S3Client:
        """Lazily create S3 client (respects AWS_PROFILE)."""
        if self._client is None:
            import boto3

            if self.region:
                self._client = boto3.client("s3", region_name=self.region)
            else:
                self._client = boto3.client("s3")
        return self._client

    def find_files_for_date(self, target_date: date | None = None) -> FileSet:
        """Find CUSIP PIP files in S3 bucket for a specific date."""
        if target_date is None:
            target_date = date.today()

        date_pattern = target_date.strftime("%m-%d")
        search_prefix = f"{self.prefix}CED{date_pattern}"

        issuer_file: FileInfo | None = None
        issue_file: FileInfo | None = None
        issue_attr_file: FileInfo | None = None

        # List objects matching the date pattern
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=search_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                name = key.split("/")[-1]  # Get filename from full key
                name_upper = name.upper()

                if not name_upper.endswith(".PIP"):
                    continue

                file_info = FileInfo(
                    name=name,
                    source="s3",
                    s3_bucket=self.bucket,
                    s3_key=key,
                )

                if name_upper.endswith("R.PIP"):
                    issuer_file = file_info
                elif name_upper.endswith("E.PIP"):
                    issue_file = file_info
                elif name_upper.endswith("A.PIP"):
                    issue_attr_file = file_info

        return FileSet(
            issuer=issuer_file,
            issue=issue_file,
            issue_attr=issue_attr_file,
            target_date=target_date,
        )

    def read_file(self, file_info: FileInfo) -> list[str]:
        """Read file contents from S3."""
        if file_info.s3_bucket is None or file_info.s3_key is None:
            raise ValueError(f"No S3 location for file: {file_info.name}")

        response = self.client.get_object(
            Bucket=file_info.s3_bucket,
            Key=file_info.s3_key,
        )
        content = response["Body"].read().decode("utf-8", errors="replace")
        return content.splitlines()


def create_file_source(
    source_type: str,
    file_dir: Path | None = None,
    s3_bucket: str | None = None,
    s3_prefix: str = "pip/",
    s3_region: str | None = None,
) -> LocalFileSource | S3FileSource:
    """
    Factory function to create the appropriate file source.

    Args:
        source_type: 'local' or 's3'
        file_dir: Directory path for local source
        s3_bucket: S3 bucket name for S3 source
        s3_prefix: S3 prefix/path for S3 source
        s3_region: AWS region for S3 source (optional)

    Returns:
        Configured file source instance

    Raises:
        ValueError: If required parameters are missing
    """
    if source_type == "local":
        if file_dir is None:
            raise ValueError("file_dir is required for local file source")
        return LocalFileSource(directory=file_dir)
    elif source_type == "s3":
        if not s3_bucket:
            raise ValueError("s3_bucket is required for S3 file source")
        return S3FileSource(
            bucket=s3_bucket,
            prefix=s3_prefix,
            region=s3_region if s3_region else None,
        )
    else:
        raise ValueError(f"Unknown file source type: {source_type}")
