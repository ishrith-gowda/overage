#!/usr/bin/env python3
"""Create ``.venv``: prefer ``--copies`` (exfat/usb); fall back if unsupported."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(".venv")
    shutil.rmtree(root, ignore_errors=True)
    env = os.environ | {"COPYFILE_DISABLE": "1"}
    exe = sys.executable
    copies = subprocess.run(
        [exe, "-m", "venv", "--copies", str(root)],
        env=env,
        check=False,
    )
    if copies.returncode != 0:
        shutil.rmtree(root, ignore_errors=True)
        subprocess.run([exe, "-m", "venv", str(root)], env=env, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
