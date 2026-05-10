#!/usr/bin/env python3
"""Fail fast if the active interpreter is below Python 3.12.

Used by `make verify-python` so `make check` never runs against Apple's
``python3`` (3.9) or other interpreters that lack ``datetime.UTC`` and violate
``requires-python`` in ``pyproject.toml``.

Reference: Phase 0 (foundation) / README prerequisites.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Exit with code 1 when ``sys.version_info`` is less than (3, 12)."""
    if sys.version_info < (3, 12):
        print(
            f"Overage requires Python 3.12+ (found {sys.version.split()[0]}). "
            "Use python3.12 and a venv — see CONTRIBUTING.md.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(f"Python OK: {sys.version.split()[0]}")


if __name__ == "__main__":
    main()
