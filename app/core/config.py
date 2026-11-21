"""
GeneWeaver - Central Application Configuration.

Manages environment variables, database settings, Redis,
sequence processing limits, and application configuration.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="GW_",
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    # --------------------------------------------------
    # Application configuration
    # --------------------------------------------------

    app_name: str = "GeneWeaver"
    app_version: str = "0.1.0"

    environment: Literal[
        "development",
        "testing",
        "production",
    ] = "development"

    debug: bool = True

    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
    ] = "INFO"

    # --------------------------------------------------
    # Database configuration
    # --------------------------------------------------

    database_url: str = (
        "postgresql+psycopg://geneweaver:change-me@localhost:5432/geneweaver"
    )

    database_echo: bool = False

    # --------------------------------------------------
    # Redis configuration
    # --------------------------------------------------

    redis_url: str = "redis://localhost:6379/0"

    # --------------------------------------------------
    # Sequence processing configuration
    # --------------------------------------------------

    max_upload_size_mb: int = Field(
        default=100,
        gt=0,
        le=1024,
    )

    max_sequence_length: int = Field(
        default=10_000_000,
        gt=0,
    )

    alignment_backend: Literal[
        "cpu",
        "gpu",
        "auto",
    ] = "cpu"

    # --------------------------------------------------
    # API configuration
    # --------------------------------------------------

    api_prefix: str = "/api/v1"

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --------------------------------------------------
    # Validators
    # --------------------------------------------------

    @field_validator("app_name", "app_version")
    @classmethod
    def validate_non_empty_strings(
        cls,
        value: str,
    ) -> str:
        """Reject empty application metadata."""

        value = value.strip()

        if not value:
            raise ValueError("Value cannot be empty.")

        return value

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(
        cls,
        value: str,
    ) -> str:
        """Ensure API prefix starts with a slash."""

        value = value.strip()

        if not value.startswith("/"):
            raise ValueError("API prefix must start with '/'.")

        return value.rstrip("/") or "/"

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(
        cls,
        value: list[str],
    ) -> list[str]:
        """Remove whitespace and reject empty origins."""

        origins = [origin.strip() for origin in value]

        if any(not origin for origin in origins):
            raise ValueError("CORS origins cannot be empty.")

        return origins


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load and cache application settings.

    Settings are loaded from environment variables
    and the local .env file.
    """

    return Settings()


# Shared application settings instance
settings = get_settings()
