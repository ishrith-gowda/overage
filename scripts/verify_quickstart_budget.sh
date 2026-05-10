#!/usr/bin/env bash
# Phase 0.10 — machine-checkable Story 7 smoke path (install + API tests).
# Simulates README “register later” prerequisites: dev dependencies only (no ML/PDF)
# so a cold install stays within the 300s budget on GitHub-hosted runners.
set -euo pipefail

START_TS=$(date +%s)
MAX_SECONDS="${QUICKSTART_MAX_SECONDS:-300}"

python3 -m pip install --upgrade pip setuptools wheel
COPYFILE_DISABLE=1 python3 -m pip install -e ".[dev]"

export DD_TRACE_ENABLED="${DD_TRACE_ENABLED:-false}"
export DD_INSTRUMENTATION_TELEMETRY_ENABLED="${DD_INSTRUMENTATION_TELEMETRY_ENABLED:-false}"

python3 -m pytest proxy/tests/test_api.py -q --timeout=120

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))
echo "quickstart_verify_elapsed_seconds=${ELAPSED}"

if ((ELAPSED > MAX_SECONDS)); then
  echo "Quickstart smoke exceeded ${MAX_SECONDS}s budget (set QUICKSTART_MAX_SECONDS to relax)."
  exit 1
fi
