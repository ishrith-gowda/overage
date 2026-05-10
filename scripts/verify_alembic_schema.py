#!/usr/bin/env python3
"""Verify Alembic-created SQLite contains core Overage tables.

Usage:
    python scripts/verify_alembic_schema.py /path/to/db.sqlite

Exit code 1 if ``users`` is missing.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def _main(db_path: Path) -> None:
    """Assert ``users`` exists after ``alembic upgrade head``."""
    url = f"sqlite+aiosqlite:///{db_path}"
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name IN ('users', 'api_keys', 'api_call_logs')"
                )
            )
            rows = {row[0] for row in result.fetchall()}
        missing = {"users", "api_keys", "api_call_logs"} - rows
        if missing:
            msg = f"Missing tables after alembic upgrade: {sorted(missing)}"
            raise SystemExit(msg)
    finally:
        await engine.dispose()


def main() -> None:
    """CLI entry."""
    if len(sys.argv) != 2:
        print("usage: verify_alembic_schema.py <path-to-sqlite-file>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(_main(Path(sys.argv[1])))


if __name__ == "__main__":
    main()
