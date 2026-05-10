# Overage

**Independent audit layer for hidden LLM reasoning token billing.**

[![CI](https://github.com/ishrith-gowda/overage/actions/workflows/ci.yml/badge.svg)](https://github.com/ishrith-gowda/overage/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ishrith-gowda/overage/branch/main/graph/badge.svg)](https://codecov.io/gh/ishrith-gowda/overage)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

---

## What is Overage?

Overage is a FastAPI reverse proxy that sits between your application and LLM providers (OpenAI, Anthropic, Google Gemini), intercepts reasoning model API calls, and independently verifies provider-reported reasoning token counts. It uses two signals: (1) a LoRA-fine-tuned Qwen2.5-1.5B estimation model based on the PALACE framework, and (2) response timing analysis that cross-validates token counts against expected generation speeds. No provider cooperation required.

## The Problem

LLM reasoning models (OpenAI o3/o4-mini, Anthropic Claude with extended thinking, Gemini Flash Thinking) generate hidden "reasoning tokens" that represent 60-90%+ of your total bill. These tokens are reported by the provider with zero independent verification. Every billing tool in the ecosystem (Stripe, CloudZero, Vantage, Helicone) passes through provider-reported numbers without questioning them. There is a structural incentive for providers to over-report reasoning tokens, and until Overage, no tool existed to independently verify these counts. If you are spending $50K+/month on LLM APIs, you are paying bills you cannot audit.

## Architecture

```mermaid
graph TB
    subgraph "Your Application"
        APP[Your App<br/>1-line base_url change]
    end

    subgraph "Overage"
        PROXY[Proxy Server<br/>FastAPI, adds less than 10ms]
        EST[Estimation Pipeline<br/>PALACE ML Model + Timing Analysis]
        DB[(Database<br/>PostgreSQL / SQLite)]
        DASH[Dashboard<br/>Streamlit]
    end

    subgraph "LLM Providers"
        OAI[OpenAI]
        ANT[Anthropic]
        GEM[Gemini]
    end

    APP -->|API call| PROXY
    PROXY -->|Forward| OAI
    PROXY -->|Forward| ANT
    PROXY -->|Forward| GEM
    OAI -->|Response| PROXY
    ANT -->|Response| PROXY
    GEM -->|Response| PROXY
    PROXY -->|Return to app| APP
    PROXY -.->|Async| EST
    EST -.->|Store| DB
    DASH -->|Read| DB
```

## Quickstart

### Prerequisites

- Python 3.12+
- Git
- (Optional) An OpenAI or Anthropic API key for live proxying

### Five-minute evaluation (Story 7)

No credit card. Goal: **register → Overage API key → prove the API accepts you** in a few commands (timings vary by machine; use `python3.12` and a fast disk).

```bash
git clone https://github.com/ishrith-gowda/overage.git && cd overage
python3.12 -m venv --copies .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
COPYFILE_DISABLE=1 make install-dev
cp .env.example .env
make run   # terminal A — wait until uvicorn is listening on :8000
```

In **terminal B**:

```bash
export BASE=http://localhost:8000
# Register — save the returned api_key as OVERAGE_API_KEY (shown once).
curl -sS -X POST "$BASE/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"eval@example.com","name":"Eval","password":"eval-pass-99"}'
export OVERAGE_API_KEY='paste ovg_live_... here'

curl -sS "$BASE/health"
curl -sS -H "X-API-Key: $OVERAGE_API_KEY" "$BASE/v1/calls"
```

You should see `healthy` from `/health` and `calls` / `total` from `/v1/calls`. Optional: create another key with `POST /v1/auth/apikey` (see [docs/API.md](./docs/API.md)). On USB/exFAT volumes, prefer `make venv-fresh` and [CONTRIBUTING.md](./CONTRIBUTING.md) troubleshooting.

**Machine-checked path (CI):** Pull requests run the **Foundation quickstart** job ([`.github/workflows/ci.yml`](./.github/workflows/ci.yml)): a fresh `pip install -e ".[dev]"` plus `pytest proxy/tests/test_api.py` must finish within **300 wall-clock seconds** on GitHub-hosted `ubuntu-latest` (`scripts/verify_quickstart_budget.sh`). That matches the minimal API surface for Story 7 without ML/PDF extras. Locally, `make verify-quickstart` runs the same script (network and disk dependent). A full `make install-dev` (torch, PDF stack) is slower on first install; use it when you need PALACE or report-generation tests.

### Setup

```bash
# Clone the repository
git clone https://github.com/ishrith-gowda/overage.git
cd overage

# Create and activate virtual environment (Makefile prefers python3.12 when installed)
python3.12 -m venv --copies .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package in editable mode (required for `import proxy` and scripts)
COPYFILE_DISABLE=1 make install-dev
# Equivalent: COPYFILE_DISABLE=1 pip install -e ".[dev]"

# Copy environment template and configure
cp .env.example .env
# Edit .env with your API keys (optional for demo mode)

# Development mode creates SQLite tables on startup. When Alembic migrations
# exist, run: make migrate

# Generate demo data (no API keys needed). Note the printed demo API key for the dashboard.
make demo

# Start the proxy server (port 8000)
make run

# In a separate terminal, start the dashboard (port 8501)
make run-dashboard

# Open the dashboard and paste your Overage API key (from `make demo` output or
# POST /v1/auth/register then POST /v1/auth/apikey).
open http://localhost:8501
```

If SQLite reports “readonly database” on some removable drives (exFAT), set `DATABASE_URL` in `.env` to a path on your local disk (for example under your home directory).

### Verify It Works

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status": "healthy", "version": "0.1.0", ...}
```

## API Usage

### Proxying an OpenAI Call

The only change to your existing code is the base URL:

```bash
# Direct OpenAI call (before)
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "o3", "messages": [{"role": "user", "content": "What is 2+2?"}]}'

# Proxied through Overage (after — same request, different URL)
curl http://localhost:8000/v1/proxy/openai \
  -H "X-API-Key: $OVERAGE_API_KEY" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "o3", "messages": [{"role": "user", "content": "What is 2+2?"}]}'
```

### Python SDK (OpenAI)

Point the client at Overage and pass your Overage API key on every request. The OpenAI SDK posts to `{base_url}/chat/completions`, which Overage exposes at `/v1/proxy/openai/chat/completions`.

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1/proxy/openai",
    api_key=os.environ["OPENAI_API_KEY"],
    default_headers={"X-API-Key": os.environ["OVERAGE_API_KEY"]},
)

response = client.chat.completions.create(
    model="o3",
    messages=[{"role": "user", "content": "Solve this math problem..."}],
)
```

Install the official SDK if needed: `pip install openai`.

### Proxying an Anthropic Call

```bash
curl http://localhost:8000/v1/proxy/anthropic \
  -H "X-API-Key: $OVERAGE_API_KEY" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":256,"messages":[{"role":"user","content":"Hello"}]}'
```

### Python SDK (Anthropic)

The Anthropic SDK posts to `{base_url}/v1/messages`. Overage exposes that at `/v1/proxy/anthropic/v1/messages` when `base_url` is `http://localhost:8000/v1/proxy/anthropic`.

```python
import os
from anthropic import Anthropic

client = Anthropic(
    base_url="http://localhost:8000/v1/proxy/anthropic",
    api_key=os.environ["ANTHROPIC_API_KEY"],
    default_headers={"X-API-Key": os.environ["OVERAGE_API_KEY"]},
)

message = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=256,
    messages=[{"role": "user", "content": "Hello"}],
)
```

Install: `pip install anthropic`.

### Latency benchmark (wire RTT)

With the proxy running (`make run` in another terminal):

```bash
make benchmark
# Equivalent: python scripts/benchmark.py --iterations 200
```

This measures round-trip time to `GET /health` (local FastAPI + HTTP baseline, not upstream provider RTT). For a **POST** through the proxy route (still without real provider latency if you mock or use a tiny payload), see `python scripts/benchmark.py --help`. Provider-facing latency and TPS calibration use `scripts/profile_tps.py` when you have API keys.

### Viewing Discrepancies

Each item in `GET /v1/calls` includes `reported_reasoning_tokens` plus, when an estimation exists, `estimated_reasoning_tokens`, `discrepancy_pct`, `timing_r_squared`, and related fields (`null` if estimation has not run yet).

```bash
# List recent calls with discrepancy data
curl http://localhost:8000/v1/calls \
  -H "X-API-Key: $OVERAGE_API_KEY"

# Get aggregate summary
curl http://localhost:8000/v1/summary \
  -H "X-API-Key: $OVERAGE_API_KEY"

# Per-provider breakdown (Story 8): group_by=provider | model | provider_model
curl "http://localhost:8000/v1/summary?group_by=provider" \
  -H "X-API-Key: $OVERAGE_API_KEY"
# Response: { "overall": { ... same fields as flat summary ... }, "groups": [ ... ] }

# Discrepancy alerts (stored rows; status=all|active|acknowledged|resolved)
curl "http://localhost:8000/v1/alerts?status=active" \
  -H "X-API-Key: $OVERAGE_API_KEY"

# Acknowledge an alert (replace ALERT_ID; idempotent)
curl -X POST "http://localhost:8000/v1/alerts/ALERT_ID/acknowledge" \
  -H "X-API-Key: $OVERAGE_API_KEY"

# PDF audit report for a date range (Story 6); writes to audit.pdf
curl -o audit.pdf "http://localhost:8000/v1/report?start_date=2026-01-01&end_date=2026-01-31" \
  -H "X-API-Key: $OVERAGE_API_KEY"
```

## Dashboard

<!-- TODO: Replace with actual screenshot after April 6 demo -->
![Overage Dashboard](docs/dashboard-placeholder.png)

*The dashboard shows: total calls audited, average discrepancy percentage, estimated dollar overcharge, per-provider breakdown, time-series discrepancy chart, and a sortable table of individual API calls with reported vs. estimated token counts.*

## Configuration

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | Database connection string | Yes |
| `OPENAI_API_KEY` | OpenAI API key for proxying | No* |
| `ANTHROPIC_API_KEY` | Anthropic API key for proxying | No* |
| `API_KEY_SECRET` | Secret for hashing Overage API keys | Yes (prod) |
| `SENTRY_DSN` | Sentry error tracking DSN | No |
| `RATE_LIMIT_PER_MINUTE` | Max requests per API key per minute | No (default: 100) |
| `PALACE_MODEL_PATH` | Path to PALACE LoRA weights | No |
| `ESTIMATION_ENABLED` | Enable async estimation pipeline | No (default: true) |

*At least one provider API key is needed for live proxying. Demo mode works without any API keys.

See [INSTRUCTIONS.md](./INSTRUCTIONS.md) for the complete environment variable reference.

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ROADMAP.md](./docs/ROADMAP.md) | **Master phase ledger — single source of truth for what Overage is building, has built, and plans to build (status, dependencies, acceptance criteria, test plans, definition of done, rollback)** |
| [INSTRUCTIONS.md](./INSTRUCTIONS.md) | Developer guide: coding standards, patterns, commands |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | Setup, commit format, PR + merge process, code review expectations |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System architecture, diagrams, technology decisions |
| [PRD.md](./PRD.md) | Product requirements, user stories, data models, API contracts |
| [docs/DEV_INFRASTRUCTURE.md](./docs/DEV_INFRASTRUCTURE.md) | Account / platform / vendor inventory and Doppler / 1Password exit criteria |
| [docs/CODECOV.md](./docs/CODECOV.md) | Codecov: GitHub secret, activation, troubleshooting |
| [.github/copilot-instructions.md](.github/copilot-instructions.md) | GitHub Copilot-specific patterns and templates |

## Development

```bash
# Run all checks (lint + typecheck + test)
make check

# Run tests only
make test

# Format code
make format

# Generate a new database migration
make migration

# See all available commands
make help
```

## Contributing

We welcome contributions. Please read [INSTRUCTIONS.md](./INSTRUCTIONS.md) for coding standards, naming conventions, and the PR process. All code must pass `make check` before merging.

Key requirements:
- Full type annotations on every function
- Google-style docstrings
- Structured logging via structlog (no print statements)
- Tests for every new feature (pytest, naming convention: `test_<func>_<scenario>_<expected>`)

## Research Foundations

Overage builds on peer-reviewed research in LLM computation verification:

- **PALACE Framework** (arXiv:2508.00912) — Prompt-based reasoning token estimation using fine-tuned language models
- **Timing Correlation** (arXiv:2412.15431) — Strong correlation (Pearson >= 0.987) between output token count and generation time
- **IMMACULATE** (arXiv:2602.22700) — Cryptographic verification approach (complementary; requires provider cooperation)

## License

MIT License. See [LICENSE](./LICENSE) for details.

---

**Overage** — Trust, but verify.
