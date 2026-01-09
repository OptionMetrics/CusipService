"""Application configuration using pydantic-settings."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _fetch_secret_from_aws(secret_arn: str, region: str | None = None) -> dict:
    """Fetch secret value from AWS Secrets Manager.

    Args:
        secret_arn: ARN or name of the secret
        region: AWS region (optional, uses default if not set)

    Returns:
        Parsed JSON secret as a dictionary
    """
    try:
        import boto3
    except ImportError as e:
        raise ImportError(
            "boto3 is required to fetch secrets from AWS Secrets Manager. "
            "Install it with: uv add boto3"
        ) from e

    client = boto3.client("secretsmanager", region_name=region or None)
    response = client.get_secret_value(SecretId=secret_arn)
    return json.loads(response["SecretString"])


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CUSIP_",
        env_file=".env",
        case_sensitive=False,
    )

    # Database - can be overridden by db_secret_arn
    db_host: str = Field(default="localhost", description="Database host")
    db_port: int = Field(default=5432, description="Database port")
    db_name: str = Field(default="cusip", description="Database name")
    db_user: str = Field(default="cusip_app", description="Database user")
    db_password: str = Field(default="", description="Database password")
    db_sslmode: str = Field(
        default="prefer",
        description="SSL mode: disable, allow, prefer, require, verify-ca, verify-full",
    )

    # AWS Secrets Manager for database credentials (overrides db_* fields if set)
    db_secret_arn: str = Field(
        default="",
        description="ARN of AWS Secrets Manager secret containing DB credentials",
    )
    db_secret_region: str = Field(
        default="",
        description="AWS region for Secrets Manager (optional)",
    )

    @model_validator(mode="after")
    def _load_db_secret(self) -> "Settings":
        """Load database credentials from Secrets Manager if ARN is provided."""
        if not self.db_secret_arn:
            return self

        logger.info("Fetching database credentials from Secrets Manager")
        secret = _fetch_secret_from_aws(
            self.db_secret_arn,
            self.db_secret_region or None,
        )

        # RDS secrets use these standard keys
        if "host" in secret:
            self.db_host = secret["host"]
        if "port" in secret:
            self.db_port = int(secret["port"])
        if "dbname" in secret:
            self.db_name = secret["dbname"]
        if "username" in secret:
            self.db_user = secret["username"]
        if "password" in secret:
            self.db_password = secret["password"]

        logger.info(f"Loaded DB credentials for {self.db_user}@{self.db_host}")
        return self

    # File source configuration
    file_source: Literal["local", "s3"] = Field(
        default="local",
        description="File source: 'local' for filesystem or 's3' for S3 bucket",
    )

    # Local file paths (used when file_source='local')
    file_dir: Path = Field(
        default=Path("/data/pip_files"),
        description="Directory containing PIP files (local source only)",
    )

    # S3 configuration (used when file_source='s3')
    s3_bucket: str = Field(
        default="",
        description="S3 bucket name for PIP files",
    )
    s3_prefix: str = Field(
        default="pip/",
        description="S3 prefix/path for PIP files (include trailing slash)",
    )
    s3_region: str = Field(
        default="",
        description="AWS region for S3 bucket (optional, uses default if not set)",
    )

    # API
    api_token: str = Field(
        default="",
        description="Bearer token for job endpoint authentication",
    )

    @property
    def db_config(self) -> dict[str, str | int]:
        """Return database config dict compatible with psycopg2."""
        return {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
            "sslmode": self.db_sslmode,
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
