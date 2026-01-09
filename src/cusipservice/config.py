"""Application configuration using pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="CUSIP_",
        env_file=".env",
        case_sensitive=False,
    )

    # Database
    db_host: str = Field(default="localhost", description="Database host")
    db_port: int = Field(default=5432, description="Database port")
    db_name: str = Field(default="cusip", description="Database name")
    db_user: str = Field(default="cusip_app", description="Database user")
    db_password: str = Field(default="", description="Database password")

    # File paths
    file_dir: Path = Field(
        default=Path("/data/pif_files"),
        description="Directory containing PIF files",
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
        }


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
