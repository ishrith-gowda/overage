"""Tests for database URL → Alembic vs ORM schema policy (Phase 0 / dev startup)."""

from __future__ import annotations

import pytest

from proxy.storage.database import _repository_root, _uses_alembic_migrations_for_schema


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
