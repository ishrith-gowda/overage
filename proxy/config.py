"""Application configuration loaded from environment variables.

Uses pydantic-settings to validate and type-check all configuration at startup.
Every environment variable is documented with Field(description=...).
Reference: INSTRUCTIONS.md Section 14 (Environment Variables).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Overage application settings.

    All values are loaded from environment variables or a .env file.
    Validation runs at startup — the app will not start with invalid config.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    overage_env: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Runtime environment",
    )
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )
    proxy_host: str = Field(default="0.0.0.0", description="Proxy bind host")  # nosec B104
    proxy_port: int = Field(default=8000, ge=1, le=65535, description="Proxy bind port")
    app_version: str = Field(default="0.1.0", description="Application version string")

    # --- Database ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///./overage_dev.db",
        description="Async database connection string",
    )

    # --- LLM Provider API Keys ---
    openai_api_key: str = Field(default="", description="OpenAI API key for proxying")
    anthropic_api_key: str = Field(default="", description="Anthropic API key for proxying")
    gemini_api_key: str = Field(default="", description="Google Gemini API key for proxying")

    # --- Provider Base URLs (overridable for testing) ---
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI API base URL",
    )
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com/v1",
        description="Anthropic API base URL",
    )

    # --- Security ---
    api_key_secret: str = Field(
        default="dev-secret-change-me-in-production",
        description="Secret for hashing Overage API keys",
    )
    rate_limit_per_minute: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Max requests per API key per minute",
    )
    cors_origins: str = Field(
        default="http://localhost:8501",
        description="Comma-separated allowed CORS origins",
    )

    # --- Estimation Model ---
    estimation_enabled: bool = Field(
        default=True,
        description="Enable the async estimation pipeline",
    )
    palace_model_path: str = Field(
        default="./models/palace-v0.1",
        description="Path to PALACE LoRA weights directory",
    )
    palace_model_version: str = Field(
        default="v0.1.0",
        description="Model version tag recorded with every estimation",
    )

    # --- Monitoring ---
    sentry_dsn: str = Field(default="", description="Sentry DSN for error tracking")
    sentry_traces_sample_rate: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Fraction of transactions to trace in Sentry",
    )
    posthog_api_key: str = Field(default="", description="PostHog analytics key")

    # --- Computed Properties ---

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.overage_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.overage_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # --- Validators ---

    @field_validator("openai_api_key")
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        """Validate OpenAI API key format if provided."""
        if v and not v.startswith(("sk-", "org-")):
            msg = "OpenAI API key must start with 'sk-' or 'org-'"
            raise ValueError(msg)
        return v

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_key(cls, v: str) -> str:
        """Validate Anthropic API key format if provided."""
        if v and not v.startswith("sk-ant-"):
            msg = "Anthropic API key must start with 'sk-ant-'"
            raise ValueError(msg)
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance.

    Uses lru_cache to ensure settings are loaded exactly once.
    Call get_settings.cache_clear() in tests to reset.

    Returns:
        The validated Settings object.
    """
    return Settings()
