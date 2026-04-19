#!/usr/bin/env bash
# Set GitHub Actions repository secret CODECOV_TOKEN from stdin or env.
#
# Usage (safest — token not in shell history):
#   gh auth status   # must be logged in with repo scope
#   export CODECOV_TOKEN='paste-from-codecov-settings'
#   ./scripts/github_secret_codecov.sh
#
# Or pipe (avoid echo):
#   pbpaste | ./scripts/github_secret_codecov.sh --stdin
#
# Requires: GitHub CLI (gh), same repo as origin remote.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO="${GITHUB_REPO:-ishrith-gowda/overage}"

if [ "${1:-}" = "--stdin" ]; then
  TOKEN="$(cat)"
else
  TOKEN="${CODECOV_TOKEN:-}"
fi

if [ -z "$TOKEN" ]; then
  echo "error: no token. Set CODECOV_TOKEN or use: pbpaste | $0 --stdin" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh (GitHub CLI) not installed" >&2
  exit 1
fi

printf '%s' "$TOKEN" | gh secret set CODECOV_TOKEN --repo "$REPO"
echo "Set CODECOV_TOKEN in GitHub Actions secrets for $REPO"
