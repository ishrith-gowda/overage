"""Smoke test: Alembic migrations apply cleanly on a fresh SQLite file (Phase 0.5).

Reference: ``docs/ROADMAP.md`` Phase 0.5.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def test_alembic_upgrade_head_creates_core_tables() -> None:
    """``alembic upgrade head`` succeeds and creates the ``users`` table."""
    repo_root = Path(__file__).resolve().parents[2]
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        db_path = Path(tmp.name)
    try:
        url = f"sqlite+aiosqlite:///{db_path}"
        env = {**os.environ, "DATABASE_URL": url}
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=repo_root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        verify_script = repo_root / "scripts" / "verify_alembic_schema.py"
        subprocess.run(
            [sys.executable, str(verify_script), str(db_path)],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    finally:
        db_path.unlink(missing_ok=True)
