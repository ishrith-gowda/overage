#!/usr/bin/env python3
"""Headless capture of the Phase 3.7 dashboard call-detail + estimation JSON panel.

Orchestrates ``demo_data`` seeding (optional), ``uvicorn`` for the proxy, ``streamlit``
for the dashboard, then uses Playwright (Chromium) to fill the sidebar API key and
save a PNG — same evidence as the manual ROADMAP runbook without hand screenshots.

Prerequisites (once per machine / venv)::

    pip install -e ".[screenshot]"
    playwright install chromium

Typical usage from the repository root. **Free ports 8000 and 8501** (stop any
local ``make run`` / ``make run-dashboard`` first). By default the script uses a
**fresh** ``artifacts/overage_screenshot.db`` so ``make demo`` can run repeatedly
without duplicate-user errors; pass ``--use-env-database`` to use ``DATABASE_URL``
from ``.env`` instead (advanced).

::

    python scripts/capture_dashboard_evidence.py

Reference: ``docs/ROADMAP.md`` (PR #52 / Phase 3.7 manual screenshot steps).
"""

from __future__ import annotations

import argparse
import atexit
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import NoReturn

import httpx

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EPHEMERAL_DB_FILE = _REPO_ROOT / "artifacts" / "overage_screenshot.db"
_EPHEMERAL_DB_URL = "sqlite+aiosqlite:///./artifacts/overage_screenshot.db"

# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

_procs: list[subprocess.Popen[bytes]] = []


def _terminate_all() -> None:
    for proc in _procs:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
            except OSError:
                proc.kill()


atexit.register(_terminate_all)


def _die(msg: str, code: int = 1) -> NoReturn:
    print(msg, file=sys.stderr)
    sys.exit(code)


def _wait_http(url: str, *, timeout_s: float, desc: str) -> None:
    deadline = time.monotonic() + timeout_s
    last_err: str | None = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code < 500:
                return
            last_err = f"HTTP {r.status_code}"
        except OSError as exc:
            last_err = str(exc)
        except httpx.HTTPError as exc:
            last_err = str(exc)
        time.sleep(0.4)
    _die(f"Timed out waiting for {desc} ({url}). Last error: {last_err}")


def _run_demo(*, calls: int, days: int, env: dict[str, str]) -> None:
    demo_py = _REPO_ROOT / "scripts" / "demo_data.py"
    r = subprocess.run(
        [sys.executable, str(demo_py), "--calls", str(calls), "--days", str(days)],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
    )
    if r.returncode != 0:
        _die(
            "make demo / demo_data.py failed. If SQLite reports database is locked, "
            "stop the proxy (port 8000) and retry.",
            r.returncode or 1,
        )


def _prepare_ephemeral_demo_database(env: dict[str, str]) -> None:
    """Point ``DATABASE_URL`` at a fresh file DB and apply Alembic migrations."""
    _EPHEMERAL_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    _EPHEMERAL_DB_FILE.unlink(missing_ok=True)
    env["DATABASE_URL"] = _EPHEMERAL_DB_URL
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
    )
    if r.returncode != 0:
        _die(
            "alembic upgrade head failed for the screenshot database. "
            "Run from the repository root with a working Alembic chain.",
            r.returncode or 1,
        )


def _spawn(cmd: list[str], *, env: dict[str, str]) -> subprocess.Popen[bytes]:
    proc = subprocess.Popen(
        cmd,
        cwd=_REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    _procs.append(proc)
    return proc


def _capture_playwright(
    *,
    dashboard_url: str,
    proxy_base: str,
    api_key: str,
    output: Path,
    full_page: bool,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        _die(
            "Playwright is not installed. Run:\n"
            "  pip install -e \".[screenshot]\"\n"
            "  playwright install chromium\n"
            f"Import error: {exc}",
        )

    out = str(output.resolve())
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(dashboard_url, wait_until="domcontentloaded", timeout=120_000)

        sidebar = page.locator('[data-testid="stSidebar"]')
        sidebar.wait_for(state="visible", timeout=60_000)
        text_inputs = sidebar.locator("input[type='text']")
        if text_inputs.count() >= 1:
            text_inputs.first.fill(proxy_base)
        pw_input = sidebar.locator("input[type='password']")
        pw_input.wait_for(state="visible", timeout=30_000)
        pw_input.fill(api_key)
        page.keyboard.press("Tab")

        page.get_by_text("Recent Calls", exact=False).wait_for(timeout=120_000)
        heading = page.get_by_role("heading", name="Call detail — full estimation block")
        heading.wait_for(state="visible", timeout=120_000)
        heading.scroll_into_view_if_needed()

        if full_page:
            page.screenshot(path=out, full_page=True)
        else:
            clip = page.evaluate(
                """() => {
  const headings = [...document.querySelectorAll("h3")];
  const h = headings.find((e) => e.innerText.includes("Call detail"));
  if (!h) return null;
  const r = h.getBoundingClientRect();
  const pad = 16;
  const x = Math.max(0, r.left + window.scrollX - pad);
  const y = Math.max(0, r.top + window.scrollY - pad);
  const w = Math.min(
    document.documentElement.scrollWidth - x,
    r.width + pad * 2 + 400,
  );
  const hgt = Math.min(document.documentElement.scrollHeight - y, 780);
  return { x, y, width: w, height: hgt };
}"""
            )
            if clip and isinstance(clip, dict):
                page.screenshot(
                    path=out,
                    clip={
                        "x": float(clip["x"]),
                        "y": float(clip["y"]),
                        "width": float(clip["width"]),
                        "height": float(clip["height"]),
                    },
                )
            else:
                page.screenshot(path=out, full_page=True)
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / "artifacts" / "dashboard_phase37_evidence.png",
        help="PNG output path (parent dirs are created).",
    )
    parser.add_argument(
        "--proxy-base",
        default="http://localhost:8000",
        help="Proxy base URL for the dashboard sidebar (must match where uvicorn listens).",
    )
    parser.add_argument(
        "--dashboard-url",
        default="http://127.0.0.1:8501",
        help="Streamlit base URL.",
    )
    parser.add_argument(
        "--skip-demo",
        action="store_true",
        help="Skip demo_data seeding (use an already-seeded DB).",
    )
    parser.add_argument(
        "--demo-calls",
        type=int,
        default=80,
        help="Forwarded to demo_data.py --calls (smaller = faster).",
    )
    parser.add_argument(
        "--demo-days",
        type=int,
        default=14,
        help="Forwarded to demo_data.py --days.",
    )
    parser.add_argument(
        "--full-page",
        action="store_true",
        help="Capture the full scrollable page instead of a crop around Call detail.",
    )
    parser.add_argument(
        "--use-env-database",
        action="store_true",
        help="Use DATABASE_URL from the environment / .env instead of a fresh "
        "artifacts/overage_screenshot.db (you manage migrations and demo seeding).",
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment,misc]
    if load_dotenv is not None:
        load_dotenv(_REPO_ROOT / ".env")

    env = os.environ.copy()
    if args.use_env_database:
        if not env.get("DATABASE_URL"):
            _die("DATABASE_URL must be set when using --use-env-database.")
    else:
        if args.skip_demo:
            _die(
                "Ephemeral database mode always seeds demo data; "
                "omit --skip-demo or pass --use-env-database."
            )
        _prepare_ephemeral_demo_database(env)

    if not args.skip_demo:
        _run_demo(calls=args.demo_calls, days=args.demo_days, env=env)

    # Import after optional .env load so DATABASE_URL is visible to uvicorn child.
    from proxy.demo_constants import DEMO_PLAINTEXT_API_KEY

    uvicorn_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "proxy.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    _spawn(uvicorn_cmd, env=env)
    _wait_http("http://127.0.0.1:8000/health", timeout_s=90.0, desc="proxy /health")

    streamlit_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "dashboard/app.py",
        "--server.port",
        "8501",
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]
    _spawn(streamlit_cmd, env=env)
    _wait_http("http://127.0.0.1:8501/", timeout_s=120.0, desc="Streamlit root")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    _capture_playwright(
        dashboard_url=args.dashboard_url,
        proxy_base=args.proxy_base,
        api_key=DEMO_PLAINTEXT_API_KEY,
        output=args.output,
        full_page=args.full_page,
    )

    _terminate_all()
    _procs.clear()

    print(f"Wrote dashboard evidence PNG to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
