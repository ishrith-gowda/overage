"""Async database engine, session factory, and FastAPI dependency.

Supports both SQLite (local dev) and PostgreSQL (production) via SQLAlchemy 2.0 async.
Reference: INSTRUCTIONS.md Section 10 (Database Patterns).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import event, text
from sqlalchemy.engine.url import make_url
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

    connect_args: dict[str, bool | int] = {}
    engine_kwargs: dict[str, Any] = {
        "echo": get_settings().debug,
        "pool_pre_ping": True,
    }
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30
        engine_kwargs["pool_pre_ping"] = False

    _engine = create_async_engine(
        url,
        connect_args=connect_args,
        **engine_kwargs,
    )
    if url.startswith("sqlite"):

        @event.listens_for(_engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn: Any, _rec: Any) -> None:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=DELETE")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

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


def _uses_alembic_migrations_for_schema(database_url: str) -> bool:
    """Return True when Alembic should own schema (Postgres or file-backed SQLite).

    Anonymous in-memory SQLite URLs use :func:`init_db` instead so local scripts
    and ephemeral databases do not require a subprocess migration step.

    Args:
        database_url: SQLAlchemy database URL string.

    Returns:
        True if ``alembic upgrade head`` should run for this URL.
    """
    u = make_url(database_url)
    if u.get_backend_name() == "postgresql":
        return True
    if u.get_backend_name() != "sqlite":
        return False
    db = u.database
    return db not in (None, ":memory:", "")


def _repository_root() -> Path:
    """Return the repository root (directory containing ``alembic.ini``)."""
    return Path(__file__).resolve().parents[2]


async def run_alembic_upgrade_head(database_url: str) -> None:
    """Apply all Alembic migrations via the CLI subprocess.

    Uses a subprocess so Alembic loads ``env.py`` the same way as ``make migrate``,
    without importing migration ``env`` from the running FastAPI process.

    Args:
        database_url: Async SQLAlchemy URL passed as ``DATABASE_URL``.

    Raises:
        RuntimeError: If the Alembic command exits non-zero.
    """
    repo_root = _repository_root()
    env = {**os.environ, "DATABASE_URL": database_url}
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        "upgrade",
        "head",
        cwd=str(repo_root),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error(
            "alembic_upgrade_failed",
            returncode=proc.returncode,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )
        msg = "Alembic upgrade failed; see logs for stdout/stderr."
        raise RuntimeError(msg)
    logger.info("alembic_upgrade_complete")


async def apply_development_schema() -> None:
    """Create or migrate the schema in development before handling requests.

    Staging and production must run ``alembic upgrade head`` from deploy/ops;
    this function only runs when ``overage_env`` is development.

    When ``OVERAGE_SKIP_APP_DB_SCHEMA`` is ``1`` (proxy test suite), this is a
    no-op; pytest fixtures create tables on the test engine instead.

    File-backed SQLite and PostgreSQL URLs run ``alembic upgrade head``.
    Ephemeral SQLite (in-memory / blank path) uses :func:`init_db`.
    """
    settings = get_settings()
    if not settings.is_development:
        return
    if os.environ.get("OVERAGE_SKIP_APP_DB_SCHEMA") == "1":
        logger.info("database_schema_skipped", reason="OVERAGE_SKIP_APP_DB_SCHEMA")
        return
    if _uses_alembic_migrations_for_schema(settings.database_url):
        await run_alembic_upgrade_head(settings.database_url)
        return
    await init_db()


async def init_db() -> None:
    """Create all tables via ORM metadata (ephemeral SQLite in development).

    File-backed development databases use :func:`apply_development_schema` and
    Alembic instead. Production uses Alembic from the release pipeline, not this.
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
