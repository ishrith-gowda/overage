#!/usr/bin/env bash
# Backup Doppler `dev` secrets to a 1Password document (one-way snapshot).
#
# Prerequisites: `doppler` and `op` logged in; 1Password CLI 2.x.
#
# Usage:
#   export OP_VAULT="Private"   # or your team vault name
#   ./scripts/backup_doppler_env_to_1password.sh
#
# The script does not print secret values to stdout.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v doppler >/dev/null 2>&1; then
  echo "error: doppler CLI not found" >&2
  exit 1
fi
if ! command -v op >/dev/null 2>&1; then
  echo "error: op (1Password CLI) not found" >&2
  exit 1
fi

VAULT="${OP_VAULT:-Private}"
TITLE="${OP_ITEM_TITLE:-Overage — Doppler dev snapshot}"
TMP="$(mktemp -t doppler-env)"
trap 'rm -f "$TMP"' EXIT

doppler secrets download --no-file --format env >"$TMP"
op document create "$TMP" --vault "$VAULT" --title "$TITLE" >/dev/null
echo "Created 1Password document: \"$TITLE\" in vault \"$VAULT\""
