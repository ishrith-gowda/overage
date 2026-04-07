"""FastAPI application entry point for the Overage proxy.

Uses the app factory pattern with a lifespan handler for startup/shutdown.
Reference: ARCHITECTURE.md Section 2 (Component Diagram).
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from proxy.api.routes import router as api_router
from proxy.api.routes import set_estimators
from proxy.config import get_settings
from proxy.estimation.aggregator import DiscrepancyAggregator
from proxy.estimation.palace import PALACEEstimator
from proxy.estimation.timing import TimingEstimator
from proxy.exceptions import AuthError, OverageError, ProviderError
from proxy.middleware.request_id import RequestIDMiddleware
from proxy.providers.anthropic import AnthropicProvider
from proxy.providers.base import provider_registry
from proxy.providers.openai import OpenAIProvider
from proxy.storage.database import (
    check_db_connection,
    close_engine,
    init_db,
    init_engine,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)

# Application start time (set in lifespan)
_start_time: float = 0.0

# Estimation singletons (set in lifespan, used by health check)
_palace_estimator: PALACEEstimator | None = None


# ---------------------------------------------------------------------------
# Structured logging configuration
# ---------------------------------------------------------------------------


def _configure_logging() -> None:
    """Configure structlog for JSON output with context variables."""
    settings = get_settings()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            (
                structlog.dev.ConsoleRenderer()
                if settings.is_development
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(settings.log_level)  # type: ignore[operator]
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ---------------------------------------------------------------------------
# Sentry initialization
# ---------------------------------------------------------------------------


def _configure_sentry() -> None:
    """Initialize Sentry error tracking if DSN is configured."""
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            environment=settings.overage_env,
            release=f"overage@{settings.app_version}",
        )
        logger.info("sentry_initialized")


# ---------------------------------------------------------------------------
# Lifespan — startup and shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan handler.

    Startup:
      - Configure logging and Sentry
      - Initialize database engine and create tables (dev mode)
      - Register LLM provider adapters
      - Load PALACE estimation model
      - Initialize timing estimator and aggregator

    Shutdown:
      - Close database connections
    """
    global _start_time, _palace_estimator  # noqa: PLW0603

    _configure_logging()
    _configure_sentry()
    settings = get_settings()

    logger.info(
        "startup_begin",
        version=settings.app_version,
        env=settings.overage_env,
        estimation_enabled=settings.estimation_enabled,
    )

    # Database
    init_engine()
    if settings.is_development:
        await init_db()

    # Register providers
    provider_registry.register(OpenAIProvider())
    provider_registry.register(AnthropicProvider())

    # Estimation pipeline
    palace = PALACEEstimator()
    if settings.estimation_enabled:
        await palace.load_model()
    _palace_estimator = palace

    timing = TimingEstimator()
    agg = DiscrepancyAggregator()
    set_estimators(palace, timing, agg)

    _start_time = time.monotonic()
    logger.info(
        "startup_complete",
        providers=provider_registry.available_providers,
        model_loaded=palace.is_loaded(),
    )

    yield

    # Shutdown
    await close_engine()
    logger.info("shutdown_complete")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        The configured FastAPI app instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Overage",
        description="Independent audit layer for LLM reasoning token billing",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    # --- Middleware (applied in reverse order) ---
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routes ---
    app.include_router(api_router)

    # --- Exception handlers ---
    app.add_exception_handler(AuthError, _auth_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ProviderError, _provider_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(OverageError, _overage_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_error_handler)

    # --- Health check ---
    @app.get("/health", tags=["system"])
    async def health_check() -> dict[str, Any]:
        """Health check endpoint. No authentication required."""
        db_ok = await check_db_connection()
        model_loaded = _palace_estimator.is_loaded() if _palace_estimator else False
        uptime = time.monotonic() - _start_time if _start_time > 0 else 0.0

        status = "healthy" if db_ok else "degraded"
        return {
            "status": status,
            "version": settings.app_version,
            "uptime_seconds": round(uptime, 1),
            "model_loaded": model_loaded,
            "db_connected": db_ok,
            "providers": provider_registry.available_providers,
        }

    return app


# ---------------------------------------------------------------------------
# Exception handlers — structured JSON error responses
# ---------------------------------------------------------------------------


async def _auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
    """Handle authentication errors (401, 429)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "error_code": exc.code,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


async def _provider_error_handler(request: Request, exc: ProviderError) -> JSONResponse:
    """Handle provider errors (502, 504)."""
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "error_code": exc.code,
            "detail": exc.extra.get("detail"),
            "request_id": getattr(request.state, "request_id", None),
        },
    )


async def _overage_error_handler(request: Request, exc: OverageError) -> JSONResponse:
    """Handle all other Overage-specific errors."""
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "error_code": exc.code,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected errors — log, capture to Sentry, return 500."""
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "error_code": "INTERNAL_ERROR",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# ---------------------------------------------------------------------------
# Module-level app instance (for uvicorn proxy.main:app)
# ---------------------------------------------------------------------------
app = create_app()
