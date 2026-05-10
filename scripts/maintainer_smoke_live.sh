#!/usr/bin/env bash
# Maintainer live smoke — hits a running Overage proxy with real HTTP (not CI).
# Prerequisites: `make run` (or equivalent) so BASE is reachable.
#
# Environment:
#   OVERAGE_BASE_URL   — default http://127.0.0.1:8000
#   OVERAGE_API_KEY    — Overage key (ovg_live_…); enables GET /v1/calls
#   OPENAI_API_KEY     — with OVERAGE_API_KEY: non-stream OpenAI via proxy
#   ANTHROPIC_API_KEY  — with OVERAGE_API_KEY: non-stream Anthropic via proxy
#   OPENAI_SMOKE_MODEL — default gpt-4o-mini
#   ANTHROPIC_SMOKE_MODEL — default claude-3-5-haiku-20241022
#
# Reference: docs/ROADMAP.md §4.2 (manual smoke), §1.3 (live provider = maintainer).
set -euo pipefail

BASE="${OVERAGE_BASE_URL:-http://127.0.0.1:8000}"
BASE="${BASE%/}"

echo "==> GET ${BASE}/health"
curl -sS -f --max-time 30 "${BASE}/health"
echo

if [[ -n "${OVERAGE_API_KEY:-}" ]]; then
  echo "==> GET ${BASE}/v1/calls"
  curl -sS -f --max-time 30 -H "X-API-Key: ${OVERAGE_API_KEY}" "${BASE}/v1/calls" | head -c 1200
  echo
else
  echo "Skip /v1/calls: set OVERAGE_API_KEY"
fi

if [[ -n "${OVERAGE_API_KEY:-}" && -n "${OPENAI_API_KEY:-}" ]]; then
  MODEL="${OPENAI_SMOKE_MODEL:-gpt-4o-mini}"
  echo "==> POST OpenAI via proxy (model ${MODEL})"
  curl -sS -f --max-time 120 \
    -H "X-API-Key: ${OVERAGE_API_KEY}" \
    -H "Authorization: Bearer ${OPENAI_API_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${MODEL}\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hi in three words.\"}],\"max_tokens\":32,\"stream\":false}" \
    "${BASE}/v1/proxy/openai/chat/completions" | head -c 1200
  echo
else
  echo "Skip OpenAI proxy smoke: set OVERAGE_API_KEY and OPENAI_API_KEY"
fi

if [[ -n "${OVERAGE_API_KEY:-}" && -n "${ANTHROPIC_API_KEY:-}" ]]; then
  AMODEL="${ANTHROPIC_SMOKE_MODEL:-claude-3-5-haiku-20241022}"
  echo "==> POST Anthropic via proxy (model ${AMODEL})"
  curl -sS -f --max-time 120 \
    -H "X-API-Key: ${OVERAGE_API_KEY}" \
    -H "x-api-key: ${ANTHROPIC_API_KEY}" \
    -H "anthropic-version: 2023-06-01" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${AMODEL}\",\"max_tokens\":64,\"messages\":[{\"role\":\"user\",\"content\":\"Say hi in three words.\"}]}" \
    "${BASE}/v1/proxy/anthropic/v1/messages" | head -c 1200
  echo
else
  echo "Skip Anthropic proxy smoke: set OVERAGE_API_KEY and ANTHROPIC_API_KEY"
fi

echo "maintainer_smoke_live_ok"
