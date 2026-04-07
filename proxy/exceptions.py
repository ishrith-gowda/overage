"""Custom exception hierarchy for the Overage proxy.

Every error in the system is typed, logged, and returns a structured JSON response.
All exceptions inherit from OverageError for unified handling.
Reference: INSTRUCTIONS.md Section 7 (Error Handling Patterns).
"""

from __future__ import annotations

from typing import Any


class OverageError(Exception):
    """Base exception for all Overage errors.

    Attributes:
        message: Human-readable error description.
        code: Machine-readable error code string (e.g. 'AUTH_ERROR').
        status_code: HTTP status code for API responses.
        extra: Optional dict of additional context for logging.
    """

    def __init__(
        self,
        message: str = "An internal error occurred",
        *,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.extra = extra or {}
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Provider errors — LLM API interaction failures
# ---------------------------------------------------------------------------


class ProviderError(OverageError):
    """Base for LLM provider errors (OpenAI, Anthropic, Gemini)."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "unknown",
        status_code: int = 502,
        extra: dict[str, Any] | None = None,
    ) -> None:
        merged = {"provider": provider, **(extra or {})}
        super().__init__(
            message=f"[{provider}] {message}",
            code="PROVIDER_ERROR",
            status_code=status_code,
            extra=merged,
        )
        self.provider = provider


class ProviderTimeoutError(ProviderError):
    """Provider did not respond within the timeout window."""

    def __init__(self, provider: str, timeout_seconds: float) -> None:
        super().__init__(
            message=f"Request timed out after {timeout_seconds}s",
            provider=provider,
            status_code=504,
            extra={"timeout_seconds": timeout_seconds},
        )


class ProviderAPIError(ProviderError):
    """Provider returned an HTTP error status."""

    def __init__(self, provider: str, status_code: int, detail: str) -> None:
        super().__init__(
            message=f"HTTP {status_code}: {detail[:500]}",
            provider=provider,
            status_code=502,
            extra={"upstream_status_code": status_code, "detail": detail[:500]},
        )
        self.upstream_status_code = status_code


# ---------------------------------------------------------------------------
# Estimation errors — ML model or timing analysis failures
# ---------------------------------------------------------------------------


class EstimationError(OverageError):
    """Base for estimation pipeline errors."""

    def __init__(self, message: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="ESTIMATION_ERROR", status_code=500, extra=extra)


class ModelNotLoadedError(EstimationError):
    """PALACE model weights are not available."""

    def __init__(self) -> None:
        super().__init__(message="PALACE estimation model is not loaded")


# ---------------------------------------------------------------------------
# Storage errors — database interaction failures
# ---------------------------------------------------------------------------


class StorageError(OverageError):
    """Base for database / storage errors."""

    def __init__(self, message: str, *, extra: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="STORAGE_ERROR", status_code=500, extra=extra)


# ---------------------------------------------------------------------------
# Auth errors — authentication and authorization failures
# ---------------------------------------------------------------------------


class AuthError(OverageError):
    """Base for authentication errors."""

    def __init__(
        self,
        message: str = "Authentication failed",
        *,
        code: str = "AUTH_ERROR",
        status_code: int = 401,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code, extra=extra)


class InvalidAPIKeyError(AuthError):
    """The provided API key is invalid or not found."""

    def __init__(self) -> None:
        super().__init__(message="Invalid or missing API key", code="INVALID_API_KEY")


class RateLimitExceededError(AuthError):
    """The API key has exceeded its rate limit."""

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window_seconds}s",
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            extra={"limit": limit, "window_seconds": window_seconds},
        )


# ---------------------------------------------------------------------------
# Config errors — startup / configuration failures
# ---------------------------------------------------------------------------


class ConfigError(OverageError):
    """Configuration is missing or invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="CONFIG_ERROR", status_code=500)
