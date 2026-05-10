"""Tests for database URL → Alembic vs ORM schema policy (Phase 0 / dev startup)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from proxy.storage.database import (
    _repository_root,
    _uses_alembic_migrations_for_schema,
    apply_development_schema,
    run_alembic_upgrade_head,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql+asyncpg://u:p@h/db", True),
        ("sqlite+aiosqlite://", False),
        ("sqlite+aiosqlite:///:memory:", False),
        ("sqlite+aiosqlite:///./overage_dev.db", True),
    ],
)
def test_uses_alembic_migrations_for_schema(url: str, expected: bool) -> None:
    """File-backed SQLite and Postgres use Alembic; ephemeral SQLite does not."""
    assert _uses_alembic_migrations_for_schema(url) is expected


def test_repository_root_contains_alembic_ini() -> None:
    """``_repository_root`` must point at the directory that has ``alembic.ini``."""
    root = _repository_root()
    assert (root / "alembic.ini").is_file()


@pytest.mark.asyncio
async def test_run_alembic_upgrade_head_invokes_cli() -> None:
    """``run_alembic_upgrade_head`` shells out to ``python -m alembic upgrade head``."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"ok\n", b""))
    with patch(
        "proxy.storage.database.asyncio.create_subprocess_exec",
        AsyncMock(return_value=mock_proc),
    ) as exec_mock:
        await run_alembic_upgrade_head("sqlite+aiosqlite:///./tmp_policy.db")
    assert exec_mock.call_count == 1
    args, kwargs = exec_mock.call_args
    assert args[1:5] == ("-m", "alembic", "upgrade", "head")
    assert kwargs["env"]["DATABASE_URL"] == "sqlite+aiosqlite:///./tmp_policy.db"


@pytest.mark.asyncio
async def test_run_alembic_upgrade_head_raises_on_nonzero_exit() -> None:
    """Non-zero Alembic exit code surfaces as ``RuntimeError``."""
    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error\n"))
    with (
        patch(
            "proxy.storage.database.asyncio.create_subprocess_exec",
            AsyncMock(return_value=mock_proc),
        ),
        pytest.raises(RuntimeError, match="Alembic upgrade failed"),
    ):
        await run_alembic_upgrade_head("sqlite+aiosqlite:///./x.db")


@pytest.mark.asyncio
async def test_apply_development_schema_skips_when_env_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``OVERAGE_SKIP_APP_DB_SCHEMA=1`` skips schema work (pytest client fixture)."""
    from proxy.config import get_settings

    monkeypatch.setenv("OVERAGE_SKIP_APP_DB_SCHEMA", "1")
    get_settings.cache_clear()
    await apply_development_schema()


@pytest.mark.asyncio
async def test_apply_development_schema_noop_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production/staging never auto-migrate from the lifespan hook."""
    from proxy.config import get_settings

    monkeypatch.setenv("OVERAGE_ENV", "production")
    get_settings.cache_clear()
    await apply_development_schema()
