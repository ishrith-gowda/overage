#!/usr/bin/env python3
"""Strip Made-with / Co-authored-by lines from stdin (for git filter-branch --msg-filter).

Example (rewrite all messages on current branch — use sparingly, then force-push):

  git filter-branch -f --msg-filter 'python3 scripts/git_strip_commit_msg.py' main
"""

from __future__ import annotations

import sys


def main() -> None:
    raw = sys.stdin.read()
    if not raw:
        return
    lines = raw.splitlines()
    kept: list[str] = []
    for line in lines:
        if line.startswith(("Made-with:", "Co-authored-by:")):
            continue
        kept.append(line)
    while kept and kept[-1] == "":
        kept.pop()
    if not kept:
        return
    sys.stdout.write("\n".join(kept) + "\n")


if __name__ == "__main__":
    main()
