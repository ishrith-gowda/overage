#!/usr/bin/env bash
# Generate coverage.xml and upload to Codecov using the official Codecov CLI binary
# (avoids pip httpx conflicts with the overage package — do not pip-install codecov-cli in .venv).
#
# Requires:
#   - CODECOV_TOKEN — repository upload token (Codecov → Configuration → General)
#   - git metadata (commit SHA, branch)
#
# Binary cache: .codecov-cli/codecov (downloaded once; gitignored)

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -z "${CODECOV_TOKEN:-}" ]; then
  echo "error: CODECOV_TOKEN is not set." >&2
  echo "  Codecov → overage → Configuration → General → Repository upload token." >&2
  echo "  export CODECOV_TOKEN='...'  or: doppler secrets set CODECOV_TOKEN=... && doppler run -- $0" >&2
  exit 1
fi

BIN_DIR="$ROOT/.codecov-cli"
BIN="$BIN_DIR/codecov"
if [ ! -x "$BIN" ]; then
  mkdir -p "$BIN_DIR"
  OS="$(uname -s)"
  case "$OS" in
    Darwin) URL="https://cli.codecov.io/latest/macos/codecov" ;;
    Linux)  URL="https://cli.codecov.io/latest/linux/codecov" ;;
    *)
      echo "error: unsupported OS for bundled Codecov binary: $OS (install: pipx install codecov-cli)" >&2
      exit 1
      ;;
  esac
  echo "Downloading Codecov CLI binary to .codecov-cli/ (one-time)..." >&2
  curl -fsSL -o "$BIN" "$URL"
  chmod +x "$BIN"
fi

PYTHON="${ROOT}/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3.12 2>/dev/null || command -v python3)"

echo "Running pytest (coverage.xml)..." >&2
"$PYTHON" -m pytest proxy/tests/ \
  -q \
  --cov=proxy \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml \
  --cov-fail-under=55 \
  --timeout=60 \
  -m "not slow"

COMMIT_SHA="$(git rev-parse HEAD)"
BRANCH="$(git branch --show-current 2>/dev/null || echo main)"
NAME="local-$(hostname -s 2>/dev/null || echo host)-$(date +%Y%m%d%H%M%S)"

echo "Uploading to Codecov (branch=$BRANCH)..." >&2
exec "$BIN" upload-process \
  --disable-search \
  -f coverage.xml \
  -t "$CODECOV_TOKEN" \
  -C "$COMMIT_SHA" \
  -B "$BRANCH" \
  -n "$NAME"
