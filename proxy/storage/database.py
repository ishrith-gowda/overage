"""Async database engine, session factory, and FastAPI dependency.

Supports both SQLite (local dev) and PostgreSQL (production) via SQLAlchemy 2.0 async.
Reference: INSTRUCTIONS.md Section 10 (Database Patterns).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from proxy.config import get_settings
from proxy.storage.models import Base

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)

# Module-level engine and session factory — initialized by init_engine()
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str | None = None) -> AsyncEngine:
    """Create the async engine and session factory.

    Called once during application startup (lifespan handler).

    Args:
        database_url: Override for the database URL (used in tests).

    Returns:
        The created AsyncEngine.
    """
    global _engine, _session_factory  # noqa: PLW0603

    url = database_url or get_settings().database_url

    # SQLite needs check_same_thread=False for async
    connect_args: dict[str, bool] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    _engine = create_async_engine(
        url,
        echo=get_settings().debug,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("database_engine_created", url=_mask_url(url))
    return _engine


def get_engine() -> AsyncEngine:
    """Return the current engine. Raises if not initialized."""
    if _engine is None:
        msg = "Database engine not initialized. Call init_engine() first."
        raise RuntimeError(msg)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory. Raises if not initialized."""
    if _session_factory is None:
        msg = "Session factory not initialized. Call init_engine() first."
        raise RuntimeError(msg)
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session.

    Commits on success, rolls back on exception.

    Yields:
        An AsyncSession that is automatically managed.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables. Used in development and testing only.

    Production uses Alembic migrations instead.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_created")


async def check_db_connection() -> bool:
    """Health check: verify the database is reachable.

    Returns:
        True if a simple query succeeds, False otherwise.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except (SQLAlchemyError, RuntimeError):
        logger.warning("database_health_check_failed")
        return False


async def close_engine() -> None:
    """Dispose of the engine connection pool. Called during shutdown."""
    global _engine, _session_factory  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        logger.info("database_engine_closed")
    _engine = None
    _session_factory = None


def _mask_url(url: str) -> str:
    """Mask password in database URL for logging."""
    if "@" in url:
        # postgresql+asyncpg://user:PASSWORD@host:5432/db → ...user:***@host...
        before_at = url.split("@", maxsplit=1)[0]
        after_at = url.split("@")[1]
        if ":" in before_at.split("//")[-1]:
            scheme_user = before_at.rsplit(":", 1)[0]
            return f"{scheme_user}:***@{after_at}"
    return url
