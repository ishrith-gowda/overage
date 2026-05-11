# INSTRUCTIONS.md — Overage Developer & AI Assistant Guide

> **This is the single source of truth for how the Overage codebase works and how to contribute to it.**
> Every developer (human or AI) must read this before writing any code.
>
> Sister documents (each is canonical for its slice):
> - [`PRD.md`](./PRD.md) — product requirements, user stories, data models, API contracts.
> - [`ARCHITECTURE.md`](./ARCHITECTURE.md) — system design, diagrams, technology decisions.
> - [`docs/ROADMAP.md`](./docs/ROADMAP.md) — master phase ledger: what is being built, what is done, dependencies, acceptance criteria, definition of done, rollback. Start there for any non-trivial change.
> - [`CONTRIBUTING.md`](./CONTRIBUTING.md) — local setup, commit format, PR + merge process.

---

## 1. PROJECT OVERVIEW

**Overage** is an independent audit layer for hidden LLM reasoning token billing. It is a FastAPI reverse proxy that sits between enterprise applications and LLM providers (OpenAI, Anthropic, Google Gemini), intercepts reasoning model API calls, and independently verifies provider-reported reasoning token counts using two methods: (1) a LoRA-fine-tuned Qwen2.5-1.5B estimation model based on the PALACE framework, and (2) response timing analysis that cross-validates token counts against expected tokens-per-second rates.

**Who it's for:** Enterprise AI platform teams and FinOps leads at companies spending $50K+/month on LLM APIs who need independent verification that provider-reported reasoning token counts match actual computation performed.

**Why it exists:** LLM providers report reasoning token counts (e.g., `completion_tokens_details.reasoning_tokens` for OpenAI, `thinking_tokens` for Anthropic) with zero independent verification. These tokens represent 60-90%+ of total billing for reasoning models like o3, o4-mini, and Claude with extended thinking. There is a structural incentive for providers to over-report, and no existing tool audits these numbers. Overage is the first independent verification layer.

**Key differentiator:** Two-signal verification (ML estimation + timing analysis) that works without any provider cooperation. Unlike IMMACULATE (which requires providers to generate cryptographic proofs) or CoIn (which requires provider-side instrumentation), Overage operates unilaterally as a drop-in proxy.

---

## 2. ARCHITECTURE SUMMARY

### High-Level Flow

```
Client App → Overage Proxy → LLM Provider (sync, <10ms added)
                  │
                  └──→ Background Task: Estimation Pipeline (async)
                              │
                              ├── PALACE Model Inference (LoRA Qwen2.5-1.5B)
                              ├── Timing Analysis (latency → estimated tokens)
                              └── Signal Aggregation + Storage → Dashboard
```

### ASCII Data Flow Diagram

```
┌─────────────┐     ┌──────────────────────────────────────────────┐     ┌──────────────┐
│             │     │              OVERAGE PROXY                    │     │              │
│  Client App │────▶│  FastAPI ── Auth ── Rate Limit ── Log        │────▶│ LLM Provider │
│  (OpenAI    │     │     │                                        │     │ (OpenAI /    │
│   SDK call) │◀────│     │    Forward request, record timing      │◀────│  Anthropic / │
│             │     │     │                                        │     │  Gemini)     │
└─────────────┘     │     ▼                                        │     └──────────────┘
                    │  Background Task (async, off critical path)   │
                    │     │                                        │
                    │     ├── Extract usage from response           │
                    │     ├── Run PALACE estimation                 │
                    │     ├── Run timing estimation                 │
                    │     ├── Aggregate signals                     │
                    │     └── Store → PostgreSQL/SQLite             │
                    └──────────────────────────────────────────────┘
                                        │
                                        ▼
                              ┌──────────────────┐
                              │   Streamlit       │
                              │   Dashboard       │
                              │  (reads from DB)  │
                              └──────────────────┘
```

### Component List

| Component | Description |
|-----------|-------------|
| **Proxy Server** | FastAPI app that receives, forwards, and returns LLM API calls with minimal latency overhead |
| **Provider Adapters** | Abstract interface + concrete implementations for OpenAI, Anthropic, Gemini |
| **Auth Middleware** | API key validation, rate limiting, tenant isolation |
| **Timing Recorder** | Captures TTFT, total latency, and streaming chunk timestamps |
| **Estimation Engine** | Runs PALACE model inference + timing analysis asynchronously |
| **Signal Aggregator** | Combines ML and timing estimates, computes confidence intervals, flags discrepancies |
| **Storage Layer** | SQLAlchemy 2.0 async ORM over PostgreSQL (prod) / SQLite (dev) |
| **Dashboard** | Streamlit app showing per-call and aggregate discrepancy data |
| **Background Worker** | FastAPI BackgroundTasks for async estimation pipeline |

---

## 3. DIRECTORY STRUCTURE

```
overage/
├── .github/
│   ├── copilot-instructions.md   # GitHub Copilot repo-level instructions
│   ├── workflows/
│   │   ├── ci.yml                # Lint, type-check, test on every PR
│   │   ├── security.yml          # Bandit + CodeQL scans
│   │   └── deploy.yml            # Deploy to Railway/DigitalOcean on merge to main
│   └── dependabot.yml            # Dependency update automation
├── src/
│   ├── overage/
│   │   ├── __init__.py           # Package init, version string
│   │   ├── main.py               # FastAPI app factory, lifespan, middleware registration
│   │   ├── config.py             # Pydantic Settings — ALL configuration lives here
│   │   ├── constants.py          # Named constants (TPS rates, thresholds, limits)
│   │   ├── exceptions.py         # Custom exception hierarchy
│   │   ├── dependencies.py       # FastAPI dependency injection (auth, db session, rate limit)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py         # Top-level router that includes all sub-routers
│   │   │   ├── proxy.py          # POST /v1/proxy/{provider} — the core proxy endpoint
│   │   │   ├── calls.py          # GET /v1/calls, GET /v1/calls/{id}
│   │   │   ├── summary.py        # GET /v1/summary, GET /v1/summary/timeseries
│   │   │   ├── report.py         # GET /v1/report — PDF audit report generation
│   │   │   ├── auth.py           # POST /v1/auth/register, POST /v1/auth/apikey
│   │   │   └── health.py         # GET /health
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Abstract provider interface (ABC)
│   │   │   ├── registry.py       # Provider registry — maps provider names to implementations
│   │   │   ├── openai.py         # OpenAI provider adapter
│   │   │   ├── anthropic.py      # Anthropic provider adapter
│   │   │   └── gemini.py         # Google Gemini provider adapter
│   │   ├── estimation/
│   │   │   ├── __init__.py
│   │   │   ├── palace.py         # PALACE model inference (LoRA Qwen2.5-1.5B)
│   │   │   ├── timing.py         # Timing-based token estimation
│   │   │   ├── aggregator.py     # Signal combination + confidence intervals
│   │   │   └── domain.py         # Domain classification for prompt routing
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── database.py       # SQLAlchemy Base, engine, session factory
│   │   │   ├── user.py           # User ORM model
│   │   │   ├── api_key.py        # APIKey ORM model
│   │   │   ├── call_log.py       # APICallLog ORM model
│   │   │   ├── estimation.py     # EstimationResult ORM model
│   │   │   └── alert.py          # DiscrepancyAlert ORM model
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── proxy.py          # Pydantic models for proxy request/response
│   │   │   ├── calls.py          # Pydantic models for call listing/detail
│   │   │   ├── summary.py        # Pydantic models for summary/timeseries
│   │   │   ├── report.py         # Pydantic models for report generation
│   │   │   ├── auth.py           # Pydantic models for auth endpoints
│   │   │   └── common.py         # Shared models (ErrorResponse, PaginatedResponse, etc.)
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── logging.py        # Request/response logging middleware
│   │   │   ├── timing.py         # Request timing middleware (adds X-Request-Time header)
│   │   │   └── cors.py           # CORS configuration
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── hashing.py        # API key hashing, prompt hashing (SHA-256)
│   │       ├── tokens.py         # Token counting utilities
│   │       └── time.py           # UTC timestamp helpers
│   └── dashboard/
│       ├── app.py                # Streamlit dashboard entry point
│       ├── pages/
│       │   ├── overview.py       # Main overview page with aggregate stats
│       │   ├── call_detail.py    # Per-call detail view
│       │   └── report.py         # Report generation page
│       └── components/
│           ├── charts.py         # Reusable chart components (Plotly)
│           └── filters.py        # Date range, provider, model filter components
├── tests/
│   ├── conftest.py               # Shared fixtures: test client, db session, mock providers
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_exceptions.py
│   │   ├── test_providers/
│   │   │   ├── test_openai.py
│   │   │   ├── test_anthropic.py
│   │   │   └── test_registry.py
│   │   ├── test_estimation/
│   │   │   ├── test_palace.py
│   │   │   ├── test_timing.py
│   │   │   └── test_aggregator.py
│   │   └── test_utils/
│   │       ├── test_hashing.py
│   │       └── test_tokens.py
│   ├── integration/
│   │   ├── test_proxy_openai.py
│   │   ├── test_proxy_anthropic.py
│   │   ├── test_estimation_pipeline.py
│   │   └── test_api_calls.py
│   └── e2e/
│       └── test_full_flow.py
├── alembic/
│   ├── alembic.ini
│   ├── env.py
│   └── versions/                 # Migration files go here
├── scripts/
│   ├── demo_data.py              # Generate synthetic discrepancy data for demos
│   ├── seed_db.py                # Seed database with test data
│   └── benchmark.py              # Benchmark proxy latency
├── .env.example                  # Template for .env (NEVER commit actual .env)
├── .pre-commit-config.yaml       # Pre-commit hooks (ruff, mypy, detect-secrets)
├── .gitignore
├── Makefile                      # All common commands
├── pyproject.toml                # Project metadata, dependencies, tool config
├── requirements.txt              # Pinned production dependencies
├── requirements-dev.txt          # Dev/test dependencies
├── docker-compose.yml            # Local dev stack
├── Dockerfile                    # Production container
├── README.md
├── INSTRUCTIONS.md               # THIS FILE
├── PRD.md                        # Product Requirements Document
├── ARCHITECTURE.md               # Architecture Document
└── LICENSE                       # MIT
```

### Directory Rules

| Directory | What goes here | What does NOT go here |
|-----------|----------------|----------------------|
| `src/overage/api/` | FastAPI route handlers only. Thin controllers that call services. | Business logic, database queries, model inference |
| `src/overage/providers/` | Provider adapter implementations. Each file = one provider. | Estimation logic, API route handlers |
| `src/overage/estimation/` | ML model inference, timing analysis, signal aggregation. | HTTP handling, database operations |
| `src/overage/models/` | SQLAlchemy ORM model definitions only. | Pydantic schemas, business logic |
| `src/overage/schemas/` | Pydantic request/response models only. | ORM models, business logic |
| `src/overage/middleware/` | FastAPI middleware classes only. | Route handlers, business logic |
| `src/overage/utils/` | Pure utility functions with no side effects. | Anything that touches the database or network |
| `tests/unit/` | Tests for individual functions/classes in isolation. | Tests requiring database, network, or multiple components |
| `tests/integration/` | Tests requiring database or multiple components. | Tests requiring external live APIs |
| `tests/e2e/` | Full end-to-end flow tests. | Unit tests, integration tests |
| `scripts/` | One-off scripts for dev/demo. Not part of the application. | Application code |
| `alembic/versions/` | Auto-generated migration files only. | Manual SQL, application code |

---

## 4. TECH STACK

| Technology | Version | Purpose | Why chosen |
|-----------|---------|---------|------------|
| **Python** | 3.12+ | Core language | Required for PyTorch + FastAPI async. 3.12 for improved error messages, `type` keyword, performance improvements. |
| **FastAPI** | 0.115+ | Web framework | Best-in-class async Python framework. Auto-generates OpenAPI docs. Native dependency injection. Pydantic integration. Chose over Flask (no async) and Django (too heavy). |
| **uvicorn** | 0.32+ | ASGI server | Standard production server for FastAPI. Chose over hypercorn (less mature) and gunicorn (WSGI, not ASGI). |
| **httpx** | 0.28+ | Async HTTP client | Forwards requests to LLM providers. Supports streaming SSE. Chose over aiohttp (less ergonomic) and requests (synchronous). |
| **SQLAlchemy** | 2.0+ | ORM + database toolkit | Async support, type-safe queries, migration integration. Chose over Tortoise ORM (less mature) and raw SQL (unmaintainable). |
| **Alembic** | 1.14+ | Database migrations | Standard migration tool for SQLAlchemy. Auto-generates migrations from model changes. |
| **Supabase** | — | Production database (PostgreSQL) | Managed Postgres with generous free tier. API layer optional. Chose over raw Postgres (more ops), Firebase (NoSQL). |
| **SQLite** | — | Local dev database | Zero-config local development. Same SQLAlchemy models work across both. |
| **PyTorch** | 2.5+ | ML inference | Required for PALACE model. Industry standard. |
| **transformers** | 4.47+ | Hugging Face model loading | Standard interface for loading Qwen2.5-1.5B. |
| **PEFT** | 0.14+ | LoRA adapter loading | Required for loading PALACE LoRA fine-tuned weights on top of base model. |
| **Streamlit** | 1.41+ | Dashboard (v0) | Fastest path to a working dashboard. Python-native. Chose over Next.js (slower to ship) for MVP. |
| **Pydantic** | 2.10+ | Data validation | Request/response validation, settings management. Deeply integrated with FastAPI. |
| **pydantic-settings** | 2.7+ | Configuration management | Loads from .env files and environment variables with type validation. |
| **structlog** | 24.4+ | Structured logging | JSON-formatted logs with context binding. Request ID propagation. Chose over stdlib logging (no structured output). |
| **Sentry SDK** | 2.19+ | Error tracking | Automatic exception capture with context. Free 50K errors via Student Pack. |
| **ruff** | 0.8+ | Linter + formatter | Replaces flake8 + black + isort in one tool. 10-100x faster. Chose over individual tools (more config, slower). |
| **mypy** | 1.13+ | Static type checking | Catches type errors before runtime. Strict mode enforced. |
| **pytest** | 8.3+ | Testing framework | Standard Python testing. Async support via pytest-asyncio. Rich plugin ecosystem. |
| **pytest-asyncio** | 0.24+ | Async test support | Required for testing async FastAPI endpoints and httpx calls. |
| **pytest-cov** | 6.0+ | Coverage reporting | Generates coverage reports for CI. |
| **bandit** | 1.8+ | Security linting | Catches common security issues (hardcoded passwords, SQL injection patterns). |
| **detect-secrets** | 1.5+ | Secret detection | Pre-commit hook to prevent accidental secret commits. |
| **Docker** | — | Containerization | Reproducible builds, local dev stack, production deployment. |

---

## 5. CODING STANDARDS

### 5.1 Python Version

Python 3.12+ is required. Use modern Python features:

```python
# CORRECT: Use 3.12+ features
type UserId = int  # Type alias (3.12+)
type ProviderName = Literal["openai", "anthropic", "gemini"]

# CORRECT: Use | instead of Union (3.10+)
def process(value: str | None) -> dict[str, Any]:
    ...

# WRONG: Old-style type hints
from typing import Union, Dict, List, Optional
def process(value: Optional[str]) -> Dict[str, Any]:  # Use str | None and dict[str, Any]
    ...
```

### 5.2 Type Annotations

Every function MUST have full type annotations. No exceptions.

```python
# CORRECT: Simple function
def hash_api_key(raw_key: str) -> str:
    """Hash an API key using SHA-256."""
    return hashlib.sha256(raw_key.encode()).hexdigest()

# CORRECT: Complex types
async def list_calls(
    user_id: int,
    provider: str | None = None,
    model: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List API calls with optional filtering."""
    ...

# CORRECT: Async generator (for streaming)
async def stream_proxy_response(
    provider: BaseProvider,
    request_data: dict[str, Any],
    api_key: str,
) -> AsyncGenerator[bytes, None]:
    """Stream SSE chunks from the LLM provider."""
    async with provider.stream(request_data, api_key) as response:
        async for chunk in response.aiter_bytes():
            yield chunk

# CORRECT: Callback / callable type
def register_hook(
    event: str,
    callback: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Register an async callback for an event."""
    ...

# CORRECT: TypedDict for structured dicts
class UsageData(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int
    total_tokens: int

# WRONG: No type annotations
def hash_api_key(raw_key):  # Missing annotations
    return hashlib.sha256(raw_key.encode()).hexdigest()

# WRONG: Using Any when a specific type is known
def get_user(user_id: Any) -> Any:  # Be specific
    ...
```

### 5.3 Ruff Configuration

Ruff replaces flake8, black, and isort. Configuration in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 99

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "A",    # flake8-builtins
    "S",    # flake8-bandit
    "T20",  # flake8-print (catches print() statements)
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "RUF",  # ruff-specific rules
]
ignore = ["S101"]  # Allow assert in tests

[tool.ruff.lint.isort]
known-first-party = ["overage"]
```

### 5.4 Mypy Strict Mode

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
check_untyped_defs = true
```

```python
# CORRECT: Module that passes mypy strict
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from overage.models.user import User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Fetch a user by their email address.

    Args:
        session: Async database session.
        email: The email address to search for.

    Returns:
        The User if found, None otherwise.
    """
    from sqlalchemy import select
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# WRONG: Module that fails mypy strict
def get_user_by_email(session, email):  # Missing annotations
    result = session.execute(...)       # Missing await
    return result.scalar_one_or_none()
```

### 5.5 Google-Style Docstrings

Every public function, class, and module MUST have a docstring.

```python
# CORRECT: Complete Google-style docstring
async def estimate_reasoning_tokens(
    prompt: str,
    answer: str,
    model: str,
    response_time_ms: float,
) -> EstimationResult:
    """Estimate the number of reasoning tokens using PALACE + timing analysis.

    Runs the PALACE LoRA model on the (prompt, answer) pair to produce a
    reasoning token count estimate, then cross-validates against the response
    timing signal. Returns a combined result with confidence intervals.

    Args:
        prompt: The input prompt sent to the LLM provider.
        answer: The response text received from the LLM provider.
        model: The model identifier (e.g., "o3", "o4-mini").
        response_time_ms: Total response time in milliseconds.

    Returns:
        EstimationResult containing the estimated token count,
        confidence interval, and signal agreement score.

    Raises:
        ModelNotLoadedError: If the PALACE model is not loaded.
        EstimationError: If the estimation pipeline fails.

    Example:
        >>> result = await estimate_reasoning_tokens(
        ...     prompt="Solve this math problem...",
        ...     answer="Let me think step by step...",
        ...     model="o3",
        ...     response_time_ms=15234.5,
        ... )
        >>> result.estimated_tokens
        8432
    """
    ...

# WRONG: Incomplete docstring
async def estimate_reasoning_tokens(prompt, answer, model, response_time_ms):
    """Estimate tokens."""  # Too brief, no Args/Returns/Raises
    ...
```

### 5.6 Async/Await Patterns

```python
# CORRECT: Async HTTP call to LLM provider
async def forward_to_openai(
    client: httpx.AsyncClient,
    request_data: dict[str, Any],
    api_key: str,
) -> httpx.Response:
    """Forward a request to the OpenAI API.

    Args:
        client: Shared async HTTP client.
        request_data: The request payload.
        api_key: The provider API key.

    Returns:
        The HTTP response from OpenAI.

    Raises:
        ProviderTimeoutError: If the request times out.
        ProviderAPIError: If OpenAI returns an error status.
    """
    try:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=request_data,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=300.0,
        )
        response.raise_for_status()
        return response
    except httpx.TimeoutException as exc:
        raise ProviderTimeoutError(provider="openai", timeout_seconds=300.0) from exc
    except httpx.HTTPStatusError as exc:
        raise ProviderAPIError(
            provider="openai",
            status_code=exc.response.status_code,
            detail=exc.response.text,
        ) from exc


# CORRECT: Async database query
async def get_calls_for_user(
    session: AsyncSession,
    user_id: int,
    limit: int = 50,
) -> list[APICallLog]:
    """Fetch recent API call logs for a user.

    Args:
        session: Async database session.
        user_id: The user's ID.
        limit: Maximum number of results.

    Returns:
        List of APICallLog records, newest first.
    """
    stmt = (
        select(APICallLog)
        .where(APICallLog.user_id == user_id)
        .order_by(APICallLog.timestamp.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# WRONG: Synchronous HTTP call in async context
async def forward_to_openai_BAD(request_data: dict, api_key: str):
    import requests  # WRONG: synchronous library in async function
    response = requests.post(  # WRONG: blocks the event loop
        "https://api.openai.com/v1/chat/completions",
        json=request_data,
    )
    return response
```

### 5.7 Structlog Usage

```python
# CORRECT: Logger initialization (top of every module)
import structlog

logger = structlog.get_logger(__name__)


# CORRECT: Logging with context binding
async def process_api_call(call_id: int, request_id: str) -> None:
    """Process an API call through the estimation pipeline."""
    log = logger.bind(call_id=call_id, request_id=request_id)
    log.info("estimation_pipeline_started")

    try:
        result = await run_palace_estimation(call_id)
        log.info(
            "palace_estimation_complete",
            estimated_tokens=result.estimated_tokens,
            confidence=result.confidence,
        )
    except EstimationError as exc:
        log.error("palace_estimation_failed", error=str(exc))
        raise


# WRONG: Using print()
async def process_api_call_BAD(call_id: int) -> None:
    print(f"Processing call {call_id}")  # WRONG: use structlog
    print(f"Result: {result}")            # WRONG: no structured context


# WRONG: Using stdlib logging
import logging  # WRONG: use structlog
logging.info("Processing call %s", call_id)  # WRONG: unstructured
```

### 5.8 Banned Patterns (Quick Reference)

| Banned | Replacement | Reason |
|--------|-------------|--------|
| `print()` | `structlog.get_logger()` | Structured logging for production |
| `from x import *` | `from x import Specific, Names` | Explicit imports prevent namespace pollution |
| `except:` or `except Exception:` | `except SpecificError as exc:` | Bare excepts hide bugs |
| `OPENAI_URL = "https://..."` | `settings.openai_base_url` | Configuration must be externalized |
| `requests.get(...)` | `await client.get(...)` | Sync HTTP blocks the async event loop |
| `cursor.execute("SELECT...")` | `session.execute(select(...))` | Raw SQL is unmaintainable and injection-prone |
| `def foo(items=[])` | `def foo(items: list | None = None)` | Mutable defaults are shared across calls |

---

## 6. NAMING CONVENTIONS

### Files

```
# snake_case, descriptive
call_log.py           ✅
api_key.py            ✅
estimation_result.py  ✅
CallLog.py            ❌  (PascalCase is for classes, not files)
apiKey.py             ❌  (camelCase is not Python)
util.py               ❌  (too vague — use hashing.py, tokens.py, time.py)
```

### Functions and Variables

```python
# snake_case, verb-first for functions
async def estimate_reasoning_tokens(...) -> ...:     ✅
async def forward_request_to_provider(...) -> ...:   ✅
async def validate_api_key(...) -> ...:              ✅
total_discrepancy_pct = 12.5                         ✅
palace_estimated_tokens = 8432                       ✅

async def EstimateTokens(...) -> ...:                ❌  (PascalCase)
async def estimateTokens(...) -> ...:                ❌  (camelCase)
x = 12.5                                            ❌  (meaningless name)
```

### Classes

```python
# PascalCase, noun
class APICallLog(Base):              ✅
class OpenAIProvider(BaseProvider):   ✅
class EstimationResult(BaseModel):   ✅
class ProviderTimeoutError(OverageError):  ✅

class api_call_log(Base):            ❌  (snake_case)
class openaiProvider(BaseProvider):  ❌  (camelCase)
```

### Constants

```python
# SCREAMING_SNAKE_CASE in constants.py
DEFAULT_RATE_LIMIT_PER_MINUTE = 100         ✅
OPENAI_O3_TOKENS_PER_SECOND = 55.0         ✅
MAX_PROMPT_LENGTH_CHARS = 100_000           ✅
PALACE_MODEL_VERSION = "v0.1.0"             ✅
ESTIMATION_CONFIDENCE_THRESHOLD = 0.85      ✅

default_rate_limit = 100                    ❌  (not SCREAMING_SNAKE_CASE)
TPS = 55.0                                 ❌  (too cryptic)
```

### Test Files and Functions

```python
# Test files: test_<module>.py
# Test functions: test_<function>_<scenario>_<expected_result>

# File: tests/unit/test_providers/test_openai.py

def test_extract_usage_valid_response_returns_usage_data():       ✅
def test_extract_usage_missing_field_raises_provider_error():     ✅
def test_extract_usage_zero_reasoning_tokens_returns_zero():      ✅
async def test_forward_request_timeout_raises_timeout_error():    ✅
async def test_forward_request_success_returns_response():        ✅

def test_openai():                                                ❌  (no scenario/expectation)
def test_it_works():                                              ❌  (meaningless)
def testExtractUsage():                                           ❌  (camelCase)
```

---

## 7. ERROR HANDLING PATTERNS

### 7.1 Custom Exception Hierarchy

```python
# src/overage/exceptions.py

class OverageError(Exception):
    """Base exception for all Overage errors.

    All custom exceptions inherit from this class so that a single
    except clause can catch any Overage-specific error.

    Attributes:
        message: Human-readable error description.
        error_code: Machine-readable error code for API responses.
    """

    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


# --- Authentication errors ---

class AuthenticationError(OverageError):
    """Raised when API key validation fails."""

    def __init__(self, detail: str = "Invalid or missing API key") -> None:
        super().__init__(message=detail, error_code="AUTH_ERROR")


class RateLimitExceededError(OverageError):
    """Raised when a user exceeds their rate limit."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window_seconds}s",
            error_code="RATE_LIMIT_EXCEEDED",
        )
        self.limit = limit
        self.window_seconds = window_seconds


# --- Provider errors ---

class ProviderError(OverageError):
    """Base exception for LLM provider errors."""

    def __init__(self, provider: str, message: str, error_code: str = "PROVIDER_ERROR") -> None:
        self.provider = provider
        super().__init__(message=f"[{provider}] {message}", error_code=error_code)


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request times out."""

    def __init__(self, provider: str, timeout_seconds: float) -> None:
        super().__init__(
            provider=provider,
            message=f"Request timed out after {timeout_seconds}s",
            error_code="PROVIDER_TIMEOUT",
        )


class ProviderAPIError(ProviderError):
    """Raised when a provider returns an error HTTP status."""

    def __init__(self, provider: str, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(
            provider=provider,
            message=f"HTTP {status_code}: {detail}",
            error_code="PROVIDER_API_ERROR",
        )


# --- Estimation errors ---

class EstimationError(OverageError):
    """Raised when the estimation pipeline fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_code="ESTIMATION_ERROR")


class ModelNotLoadedError(EstimationError):
    """Raised when the PALACE model is not loaded."""

    def __init__(self) -> None:
        super().__init__(message="PALACE estimation model is not loaded")


# --- Validation errors ---

class ValidationError(OverageError):
    """Raised when request validation fails."""

    def __init__(self, field: str, detail: str) -> None:
        super().__init__(
            message=f"Validation error on '{field}': {detail}",
            error_code="VALIDATION_ERROR",
        )
```

### 7.2 Correct Error Handling Patterns

```python
# CORRECT: API call to OpenAI with proper error handling
async def forward_to_provider(
    client: httpx.AsyncClient,
    provider: str,
    url: str,
    payload: dict[str, Any],
    api_key: str,
) -> dict[str, Any]:
    """Forward request to LLM provider with structured error handling."""
    log = logger.bind(provider=provider)

    try:
        response = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=300.0,
        )
        response.raise_for_status()
        return response.json()

    except httpx.TimeoutException as exc:
        log.error("provider_timeout", url=url)
        raise ProviderTimeoutError(provider=provider, timeout_seconds=300.0) from exc

    except httpx.HTTPStatusError as exc:
        log.error(
            "provider_api_error",
            status_code=exc.response.status_code,
            body=exc.response.text[:500],
        )
        raise ProviderAPIError(
            provider=provider,
            status_code=exc.response.status_code,
            detail=exc.response.text[:500],
        ) from exc

    except httpx.RequestError as exc:
        log.error("provider_connection_error", error=str(exc))
        raise ProviderError(
            provider=provider,
            message=f"Connection error: {exc}",
        ) from exc


# CORRECT: Database query with error handling
async def get_call_by_id(session: AsyncSession, call_id: int) -> APICallLog:
    """Fetch a single API call log by ID."""
    try:
        stmt = select(APICallLog).where(APICallLog.id == call_id)
        result = await session.execute(stmt)
        call = result.scalar_one_or_none()
        if call is None:
            raise ValidationError(field="call_id", detail=f"Call {call_id} not found")
        return call
    except SQLAlchemyError as exc:
        logger.error("database_query_failed", call_id=call_id, error=str(exc))
        raise OverageError(message="Database query failed") from exc
```

### 7.3 Error Response Format

```python
# All API errors return this format
# src/overage/schemas/common.py
class ErrorResponse(BaseModel):
    """Standard error response returned by all API endpoints."""

    error: str
    error_code: str
    detail: str | None = None
    request_id: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Rate limit exceeded: 100 requests per 60s",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "detail": None,
                "request_id": "req_abc123",
            }
        }
    )


# Global exception handler in main.py
@app.exception_handler(OverageError)
async def overage_error_handler(request: Request, exc: OverageError) -> JSONResponse:
    """Handle all Overage-specific exceptions."""
    status_map = {
        "AUTH_ERROR": 401,
        "RATE_LIMIT_EXCEEDED": 429,
        "VALIDATION_ERROR": 422,
        "PROVIDER_TIMEOUT": 504,
        "PROVIDER_API_ERROR": 502,
        "ESTIMATION_ERROR": 500,
        "INTERNAL_ERROR": 500,
    }
    status_code = status_map.get(exc.error_code, 500)

    sentry_sdk.capture_exception(exc)

    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=exc.message,
            error_code=exc.error_code,
            request_id=getattr(request.state, "request_id", None),
        ).model_dump(),
    )
```

### 7.4 Anti-Pattern: What NOT To Do

```python
# WRONG: Bare except swallows all errors
try:
    result = await client.post(url, json=payload)
except:  # NEVER do this
    pass  # Silently swallows errors, including KeyboardInterrupt

# WRONG: Catching too broadly
try:
    result = await client.post(url, json=payload)
except Exception:  # Too broad — catch specific httpx exceptions
    return None  # Returning None on error hides failures

# WRONG: Nested try/except too deep
try:
    try:
        try:  # NEVER nest more than 2 levels — refactor into functions
            result = await process(data)
        except ValueError:
            ...
    except TypeError:
        ...
except RuntimeError:
    ...
```

---

## 8. TESTING STANDARDS

### 8.1 Complete Test File Example

```python
# tests/unit/test_providers/test_openai.py
"""Tests for the OpenAI provider adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from overage.exceptions import ProviderAPIError, ProviderTimeoutError
from overage.providers.openai import OpenAIProvider


@pytest.fixture
def openai_provider() -> OpenAIProvider:
    """Create an OpenAI provider instance for testing."""
    return OpenAIProvider(base_url="https://api.openai.com/v1")


@pytest.fixture
def sample_openai_response() -> dict[str, Any]:
    """Create a sample OpenAI chat completion response."""
    return {
        "id": "chatcmpl-abc123",
        "object": "chat.completion",
        "model": "o3",
        "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 150,
            "total_tokens": 200,
            "completion_tokens_details": {
                "reasoning_tokens": 120,
                "accepted_prediction_tokens": 0,
                "rejected_prediction_tokens": 0,
            },
        },
    }


class TestExtractUsage:
    """Tests for OpenAIProvider.extract_usage()."""

    def test_extract_usage_valid_response_returns_usage_data(
        self,
        openai_provider: OpenAIProvider,
        sample_openai_response: dict[str, Any],
    ) -> None:
        """Extract usage data from a valid OpenAI response."""
        usage = openai_provider.extract_usage(sample_openai_response)

        assert usage["prompt_tokens"] == 50
        assert usage["completion_tokens"] == 150
        assert usage["reasoning_tokens"] == 120
        assert usage["total_tokens"] == 200

    def test_extract_usage_missing_reasoning_tokens_returns_zero(
        self,
        openai_provider: OpenAIProvider,
        sample_openai_response: dict[str, Any],
    ) -> None:
        """Return 0 reasoning tokens when the field is missing."""
        del sample_openai_response["usage"]["completion_tokens_details"]

        usage = openai_provider.extract_usage(sample_openai_response)

        assert usage["reasoning_tokens"] == 0

    def test_extract_usage_missing_usage_field_raises_provider_error(
        self,
        openai_provider: OpenAIProvider,
    ) -> None:
        """Raise ProviderAPIError when 'usage' field is absent."""
        response_data = {"id": "chatcmpl-abc123", "choices": []}

        with pytest.raises(ProviderAPIError, match="Missing 'usage' field"):
            openai_provider.extract_usage(response_data)


class TestForwardRequest:
    """Tests for OpenAIProvider.forward_request()."""

    @pytest.mark.asyncio
    async def test_forward_request_success_returns_response(
        self,
        openai_provider: OpenAIProvider,
        sample_openai_response: dict[str, Any],
    ) -> None:
        """Successfully forward a request and return the provider response."""
        mock_response = httpx.Response(200, json=sample_openai_response)
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response

        result = await openai_provider.forward_request(
            client=mock_client,
            payload={"model": "o3", "messages": [{"role": "user", "content": "Hi"}]},
            api_key="sk-test-key",
        )

        assert result == sample_openai_response
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_forward_request_timeout_raises_timeout_error(
        self,
        openai_provider: OpenAIProvider,
    ) -> None:
        """Raise ProviderTimeoutError when the request times out."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.side_effect = httpx.TimeoutException("Timed out")

        with pytest.raises(ProviderTimeoutError):
            await openai_provider.forward_request(
                client=mock_client,
                payload={"model": "o3", "messages": []},
                api_key="sk-test-key",
            )
```

### 8.2 Parametrized Test Example

```python
@pytest.mark.parametrize(
    ("model", "expected_tps"),
    [
        ("o3", 55.0),
        ("o4-mini", 80.0),
        ("claude-3.5-sonnet", 65.0),
        ("gemini-2.0-flash-thinking", 70.0),
    ],
    ids=["openai-o3", "openai-o4-mini", "anthropic-sonnet", "gemini-flash"],
)
def test_get_tokens_per_second_known_models_returns_correct_tps(
    model: str,
    expected_tps: float,
) -> None:
    """Return the correct TPS rate for known models."""
    from overage.estimation.timing import get_tokens_per_second

    assert get_tokens_per_second(model) == expected_tps
```

### 8.3 Async Test Pattern

```python
@pytest.mark.asyncio
async def test_estimation_pipeline_processes_call_and_stores_result(
    db_session: AsyncSession,
    mock_palace_model: AsyncMock,
) -> None:
    """Full estimation pipeline: call → PALACE + timing → store result."""
    # Arrange
    call_log = APICallLog(
        user_id=1,
        provider="openai",
        model="o3",
        reported_reasoning_tokens=10000,
        total_latency_ms=18500.0,
    )
    db_session.add(call_log)
    await db_session.flush()

    mock_palace_model.estimate.return_value = PalaceEstimate(
        estimated_tokens=8200,
        confidence_low=7800,
        confidence_high=8600,
    )

    # Act
    from overage.estimation.aggregator import run_estimation_pipeline
    result = await run_estimation_pipeline(db_session, call_log.id)

    # Assert
    assert result.palace_estimated_tokens == 8200
    assert result.timing_estimated_tokens == pytest.approx(18500.0 / 1000 * 55.0, rel=0.1)
    assert result.call_id == call_log.id
```

### 8.4 Test Anti-Patterns

```python
# WRONG: Test with no assertions
def test_it_runs():
    result = process_data({"key": "value"})
    # No assert! This test always passes.

# WRONG: Testing implementation, not behavior
def test_internal_cache_dict_has_correct_keys():
    provider = OpenAIProvider()
    assert "_cache" in provider.__dict__  # Testing internals, not behavior

# WRONG: Hardcoded magic values
def test_math():
    assert compute_discrepancy(10000, 8200) == 18.0  # Where did 18.0 come from?

# CORRECT: Self-documenting
def test_compute_discrepancy_overcounting_returns_positive_percentage():
    reported = 10000
    estimated = 8200
    expected_pct = (reported - estimated) / estimated * 100  # ~21.95%
    assert compute_discrepancy(reported, estimated) == pytest.approx(expected_pct, rel=0.01)
```

---

## 9. GIT WORKFLOW

### 9.1 Branch Naming

```
feat/proxy-openai-adapter          # New feature
feat/estimation-palace-inference   # New feature
fix/timing-estimation-overflow     # Bug fix
docs/architecture-diagram-update   # Documentation
refactor/provider-base-interface   # Refactoring
test/proxy-integration-tests       # Test additions
ci/add-codecov-upload              # CI/CD changes
chore/update-dependencies          # Maintenance
```

### 9.2 Commit Messages (Conventional Commits)

**Rules (strictly enforced):**

1. **All lowercase** — the entire commit message must be lowercase, no exceptions
2. **Single line only** — never use multi-line commit messages (no body, no description)
3. **No trailers** — never include `Co-authored-by:`, `Made-with:`, `Signed-off-by:`, or any other trailer
4. **One logical unit per commit** — each commit should be as specific as possible; prefer many small commits over few large ones
5. **Conventional prefix** — always start with `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, or `chore:`

```
feat: add openai provider adapter with usage extraction
feat: implement palace model inference endpoint
feat: add timing-based token estimation
feat: create streamlit dashboard overview page
fix: handle missing reasoning_tokens field in openai response
fix: prevent division by zero in discrepancy calculation
docs: add architecture diagram
docs: update quickstart instructions in readme
refactor: extract provider registration into factory pattern
refactor: split estimation module into palace, timing, aggregator
test: add unit tests for openai usage extraction
test: add integration tests for proxy endpoint
ci: add mypy strict mode to ci pipeline
ci: configure codecov coverage upload
chore: update fastapi to 0.115.6
chore: pin all dependencies in requirements.txt
```

**Wrong:**
```
feat: Add OpenAI Provider    ← uppercase
Fix: handle error            ← wrong prefix case
feat: add auth               ← too vague

feat: add user auth          ← multi-line (has body below)

This adds JWT-based auth...

Made-with: Cursor            ← trailer present
```

### 9.3 PR Process

1. Create feature branch from `main`
2. Write code following all conventions in this document
3. Ensure `make lint`, `make typecheck`, `make test` all pass locally
4. Push branch, open PR against `main`
5. PR description must include: what changed, why, how to test
6. At least 1 approval required (or self-merge for solo development with CI passing)
7. Squash merge into `main`
8. Delete feature branch after merge

### 9.4 Release Process

```bash
# Tag a release
git tag -a v0.1.0 -m "MVP release: proxy + estimation + dashboard"
git push origin v0.1.0

# Semantic versioning: MAJOR.MINOR.PATCH
# v0.x.x = pre-production
# v1.0.0 = first production release
```

---

## 10. DATABASE PATTERNS

### 10.1 SQLAlchemy 2.0 Async Patterns

```python
# CORRECT: Async session usage
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass

# Engine and session factory (created once in database.py)
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

# CORRECT: Dependency injection for database sessions
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session as a FastAPI dependency.

    Yields:
        An async database session that auto-commits on success
        and auto-rolls-back on exception.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# CORRECT: Query pattern with proper select()
async def get_recent_calls(
    session: AsyncSession,
    user_id: int,
    provider: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[APICallLog]:
    """Fetch recent API calls with optional filtering."""
    stmt = (
        select(APICallLog)
        .where(APICallLog.user_id == user_id)
    )
    if provider is not None:
        stmt = stmt.where(APICallLog.provider == provider)
    stmt = stmt.order_by(APICallLog.timestamp.desc()).limit(limit).offset(offset)

    result = await session.execute(stmt)
    return list(result.scalars().all())


# CORRECT: Transaction handling for multi-step operations
async def create_call_and_estimation(
    session: AsyncSession,
    call_data: dict[str, Any],
    estimation_data: dict[str, Any],
) -> tuple[APICallLog, EstimationResult]:
    """Create a call log and its estimation result atomically."""
    call = APICallLog(**call_data)
    session.add(call)
    await session.flush()  # Get the generated call.id

    estimation = EstimationResult(call_id=call.id, **estimation_data)
    session.add(estimation)
    # commit happens in the get_db_session() dependency
    return call, estimation


# WRONG: Raw SQL string
async def get_calls_BAD(session: AsyncSession, user_id: int):
    # NEVER use raw SQL strings — use SQLAlchemy select()
    result = await session.execute(
        f"SELECT * FROM api_call_logs WHERE user_id = {user_id}"  # SQL INJECTION!
    )
    return result.fetchall()
```

### 10.2 Alembic Migration Workflow

```bash
# Generate a new migration after changing a model
alembic revision --autogenerate -m "add thinking_tokens column to api_call_logs"

# ALWAYS review the generated migration file before applying!
# Check: alembic/versions/<hash>_add_thinking_tokens_column.py

# Apply migrations
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Show current migration state
alembic current

# Show migration history
alembic history
```

### 10.3 Adding a New Table

1. Create the ORM model in `src/overage/models/new_table.py`
2. Import it in `src/overage/models/__init__.py` (so Alembic sees it)
3. Run `alembic revision --autogenerate -m "create new_table table"`
4. Review the generated migration file
5. Run `alembic upgrade head`
6. Write tests

---

## 11. API ENDPOINT PATTERNS

### 11.1 Complete Endpoint Example

```python
# src/overage/api/calls.py
"""API call listing and detail endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from overage.dependencies import get_current_user, get_db_session
from overage.exceptions import ValidationError
from overage.models.call_log import APICallLog
from overage.models.user import User
from overage.schemas.calls import CallDetailResponse, CallListResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/calls", tags=["calls"])


@router.get("", response_model=CallListResponse)
async def list_calls(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    provider: Annotated[str | None, Query(description="Filter by provider name")] = None,
    model: Annotated[str | None, Query(description="Filter by model name")] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Results per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> CallListResponse:
    """List API calls for the authenticated user with optional filters.

    Args:
        session: Database session (injected).
        current_user: Authenticated user (injected).
        provider: Optional provider filter.
        model: Optional model filter.
        limit: Maximum results to return.
        offset: Pagination offset.

    Returns:
        Paginated list of API call records.
    """
    log = logger.bind(user_id=current_user.id, provider=provider, model=model)
    log.info("list_calls_requested")

    stmt = select(APICallLog).where(APICallLog.user_id == current_user.id)
    if provider:
        stmt = stmt.where(APICallLog.provider == provider)
    if model:
        stmt = stmt.where(APICallLog.model == model)
    stmt = stmt.order_by(APICallLog.timestamp.desc()).limit(limit).offset(offset)

    result = await session.execute(stmt)
    calls = list(result.scalars().all())

    log.info("list_calls_complete", count=len(calls))
    return CallListResponse(calls=calls, total=len(calls), limit=limit, offset=offset)


@router.get("/{call_id}", response_model=CallDetailResponse)
async def get_call_detail(
    call_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CallDetailResponse:
    """Get detailed information about a specific API call.

    Args:
        call_id: The call log ID.
        session: Database session (injected).
        current_user: Authenticated user (injected).

    Returns:
        Detailed call record including estimation results.

    Raises:
        ValidationError: If the call is not found or doesn't belong to this user.
    """
    stmt = (
        select(APICallLog)
        .where(APICallLog.id == call_id, APICallLog.user_id == current_user.id)
    )
    result = await session.execute(stmt)
    call = result.scalar_one_or_none()

    if call is None:
        raise ValidationError(field="call_id", detail=f"Call {call_id} not found")

    return CallDetailResponse.model_validate(call)
```

### 11.2 Anti-Pattern: What NOT To Do

```python
# WRONG: Business logic in route handler, no validation, no error handling
@router.get("/calls")
async def list_calls(provider: str = None):  # Missing type annotations
    # WRONG: No auth dependency
    # WRONG: Direct engine usage instead of session dependency
    engine = create_engine("sqlite:///dev.db")  # WRONG: hardcoded
    with engine.connect() as conn:
        # WRONG: Raw SQL
        result = conn.execute(f"SELECT * FROM calls WHERE provider = '{provider}'")
        return result.fetchall()  # WRONG: No response model, no error handling
```

---

## 12. PROVIDER IMPLEMENTATION PATTERNS

### 12.1 Abstract Provider Interface

```python
# src/overage/providers/base.py
"""Abstract base class for LLM provider adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx


class BaseProvider(ABC):
    """Abstract interface that all provider adapters must implement.

    To add a new provider:
    1. Create a new file in src/overage/providers/
    2. Implement this interface
    3. Register the provider in registry.py
    4. Add tests in tests/unit/test_providers/
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'openai', 'anthropic', 'gemini')."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for the provider API."""
        ...

    @abstractmethod
    async def forward_request(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        """Forward a request to the provider and return the response.

        Args:
            client: Shared async HTTP client.
            payload: The request body.
            api_key: The provider API key.

        Returns:
            The parsed JSON response from the provider.

        Raises:
            ProviderTimeoutError: Request timed out.
            ProviderAPIError: Provider returned an error.
        """
        ...

    @abstractmethod
    def extract_usage(self, response_data: dict[str, Any]) -> dict[str, int]:
        """Extract token usage from the provider response.

        Must return a dict with at minimum:
        - prompt_tokens: int
        - completion_tokens: int
        - reasoning_tokens: int (0 if not a reasoning model)
        - total_tokens: int

        Args:
            response_data: The parsed JSON response.

        Returns:
            Normalized usage dictionary.

        Raises:
            ProviderAPIError: If required usage fields are missing.
        """
        ...

    @abstractmethod
    def get_model_from_response(self, response_data: dict[str, Any]) -> str:
        """Extract the model name from the provider response.

        Args:
            response_data: The parsed JSON response.

        Returns:
            The model identifier string.
        """
        ...
```

### 12.2 Reference Implementation: OpenAI

```python
# src/overage/providers/openai.py
"""OpenAI provider adapter."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from overage.exceptions import ProviderAPIError, ProviderTimeoutError
from overage.providers.base import BaseProvider

logger = structlog.get_logger(__name__)


class OpenAIProvider(BaseProvider):
    """Adapter for the OpenAI Chat Completions API.

    Handles request forwarding and usage extraction for OpenAI models,
    including reasoning token extraction from o-series models.
    """

    def __init__(self, base_url: str = "https://api.openai.com/v1") -> None:
        self._base_url = base_url

    @property
    def name(self) -> str:
        return "openai"

    @property
    def base_url(self) -> str:
        return self._base_url

    async def forward_request(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        """Forward request to OpenAI Chat Completions endpoint."""
        url = f"{self.base_url}/chat/completions"
        log = logger.bind(provider=self.name, model=payload.get("model"))

        try:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=300.0,
            )
            response.raise_for_status()
            data = response.json()
            log.info("openai_request_success", model=data.get("model"))
            return data

        except httpx.TimeoutException as exc:
            log.error("openai_request_timeout")
            raise ProviderTimeoutError(provider=self.name, timeout_seconds=300.0) from exc

        except httpx.HTTPStatusError as exc:
            log.error("openai_request_error", status_code=exc.response.status_code)
            raise ProviderAPIError(
                provider=self.name,
                status_code=exc.response.status_code,
                detail=exc.response.text[:500],
            ) from exc

    def extract_usage(self, response_data: dict[str, Any]) -> dict[str, int]:
        """Extract token usage from OpenAI response.

        For o-series models, reasoning tokens are at:
        response.usage.completion_tokens_details.reasoning_tokens
        """
        usage = response_data.get("usage")
        if usage is None:
            raise ProviderAPIError(
                provider=self.name,
                status_code=200,
                detail="Missing 'usage' field in response",
            )

        completion_details = usage.get("completion_tokens_details", {})

        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "reasoning_tokens": completion_details.get("reasoning_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    def get_model_from_response(self, response_data: dict[str, Any]) -> str:
        """Extract model name from OpenAI response."""
        return response_data.get("model", "unknown")
```

### 12.3 Provider Registry

```python
# src/overage/providers/registry.py
"""Provider registry — maps provider names to implementations."""

from __future__ import annotations

from overage.exceptions import ValidationError
from overage.providers.anthropic import AnthropicProvider
from overage.providers.base import BaseProvider
from overage.providers.gemini import GeminiProvider
from overage.providers.openai import OpenAIProvider

_PROVIDERS: dict[str, type[BaseProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_provider(name: str) -> BaseProvider:
    """Get a provider instance by name.

    Args:
        name: The provider name (e.g., 'openai').

    Returns:
        An instance of the requested provider.

    Raises:
        ValidationError: If the provider name is not registered.
    """
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise ValidationError(
            field="provider",
            detail=f"Unknown provider '{name}'. Available: {list(_PROVIDERS.keys())}",
        )
    return provider_cls()


def register_provider(name: str, provider_cls: type[BaseProvider]) -> None:
    """Register a new provider.

    Args:
        name: The provider name.
        provider_cls: The provider class (must inherit from BaseProvider).
    """
    _PROVIDERS[name] = provider_cls
```

---

## 13. SECRETS MANAGEMENT

### Local Development

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your real keys
# .env is in .gitignore — NEVER commit it
```

```python
# src/overage/config.py — loads from .env automatically
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./overage_dev.db"
    sentry_dsn: str = ""
    # ... (see Section 14 for complete list)
```

### CI (GitHub Actions)

```yaml
# .github/workflows/ci.yml
env:
  DATABASE_URL: "sqlite+aiosqlite:///./test.db"
  # Secrets are set in GitHub repo Settings → Secrets and Variables → Actions
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  SENTRY_DSN: ${{ secrets.SENTRY_DSN }}
```

### Production

Environment variables are set in the hosting platform (Railway, DigitalOcean, Render).
Never pass secrets via command-line arguments or config files in production.

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml (excerpt)
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
    - id: detect-secrets
      args: ['--baseline', '.secrets.baseline']
```

### Anti-Pattern

```python
# WRONG: Hardcoded secret
OPENAI_KEY = "sk-abc123realkey"  # NEVER hardcode secrets

# WRONG: Committed .env file
# If .env is in your git status, you have a problem.
# Add .env to .gitignore immediately.
```

---

## 14. ENVIRONMENT VARIABLES

| Variable | Description | Required | Default | Example |
|----------|-------------|----------|---------|---------|
| `OVERAGE_ENV` | Runtime environment | No | `development` | `production` |
| `DEBUG` | Enable debug mode | No | `false` | `true` |
| `LOG_LEVEL` | Logging level | No | `INFO` | `DEBUG` |
| `DATABASE_URL` | Database connection string | Yes | `sqlite+aiosqlite:///./overage_dev.db` | `postgresql+asyncpg://user:pass@host:5432/overage` |
| `OPENAI_API_KEY` | OpenAI API key for proxying | No | `""` | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key for proxying | No | `""` | `sk-ant-...` |
| `GEMINI_API_KEY` | Google Gemini API key | No | `""` | `AIza...` |
| `PROXY_HOST` | Proxy server bind host | No | `0.0.0.0` | `127.0.0.1` |
| `PROXY_PORT` | Proxy server bind port | No | `8000` | `8080` |
| `API_KEY_SECRET` | Secret for hashing API keys | Yes (prod) | `dev-secret-change-me` | `<random 64-char hex>` |
| `RATE_LIMIT_PER_MINUTE` | Max requests per API key per minute | No | `100` | `500` |
| `SENTRY_DSN` | Sentry error tracking DSN | No | `""` | `https://...@sentry.io/...` |
| `PALACE_MODEL_PATH` | Path to PALACE LoRA weights | No | `./models/palace-v0.1` | `/opt/models/palace-v0.1` |
| `ESTIMATION_ENABLED` | Enable async estimation pipeline | No | `true` | `false` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | No | `http://localhost:8501` | `https://app.overage.dev` |
| `POSTHOG_API_KEY` | PostHog analytics key | No | `""` | `phc_...` |
| `DATADOG_API_KEY` | Datadog APM key | No | `""` | `dd-...` |

---

## 15. COMMON COMMANDS

All commands are available via `make`. Run `make help` for descriptions.

| Command | Description | Expected Output |
|---------|-------------|-----------------|
| `make install` | Install all dependencies (prod + dev) | Packages installed |
| `make run` | Start the proxy server (uvicorn, port 8000) | `Uvicorn running on http://0.0.0.0:8000` |
| `make run-dashboard` | Start the Streamlit dashboard (port 8501) | `You can now view your Streamlit app` |
| `make dashboard-screenshot` | Headless PNG of call-detail + estimation (Playwright; needs `pip install -e ".[screenshot]"` + `playwright install chromium`) | `Wrote dashboard evidence PNG to artifacts/...` |
| `make lint` | Run ruff linter + formatter check | `All checks passed!` or error list |
| `make format` | Auto-format with ruff | Files reformatted |
| `make typecheck` | Run mypy in strict mode | `Success: no issues found` or error list |
| `make test` | Run all tests with pytest | Test results + coverage |
| `make test-unit` | Run unit tests only | Unit test results |
| `make test-integration` | Run integration tests only | Integration test results |
| `make coverage` | Run tests with HTML coverage report | `htmlcov/index.html` generated |
| `make security` | Run bandit, `detect-secrets` (baseline), and `pip-audit` on the active Python env | Reports (`pip-audit` advisories are non-blocking via `\|\| true`) |
| `make strip-macos-appledouble` | Delete macOS AppleDouble `._*` under `proxy/`, `proxy/tests/`, `dashboard/` | Prevents Alembic/bandit failures on exFAT/USB |
| `make smoke-live` | Maintainer live HTTP checks (`scripts/maintainer_smoke_live.sh`; needs `make run` + optional provider keys) | Curl output |
| `make check` | Run lint + typecheck + test (full CI locally) | All checks pass/fail |
| `make migrate` | Apply pending Alembic migrations | `Running upgrade` messages |
| `make migration` | Auto-generate a new migration | `Generating ...versions/<hash>.py` |
| `make seed` | Seed database with test data | `Seeded N records` |
| `make demo` | Generate synthetic demo data | `Demo data generated` |
| `make clean` | Remove caches, build artifacts, .pyc files | Cleaned |
| `make docker-build` | Build Docker image | Image built |
| `make docker-up` | Start docker-compose stack | All services running |
| `make docker-down` | Stop docker-compose stack | All services stopped |

---

## 16. ANTI-PATTERNS

This section is critical for AI coding assistants. Every anti-pattern includes a **WRONG** example and the **CORRECT** replacement.

### 16.1 No print() Statements

```python
# WRONG
print(f"Processing call {call_id}")

# CORRECT
import structlog
logger = structlog.get_logger(__name__)
logger.info("processing_call", call_id=call_id)
```

### 16.2 No Bare Except Clauses

```python
# WRONG
try:
    result = await process(data)
except:
    pass

# CORRECT
try:
    result = await process(data)
except SpecificError as exc:
    logger.error("process_failed", error=str(exc))
    raise
```

### 16.3 No Star Imports

```python
# WRONG
from overage.models import *
from typing import *

# CORRECT
from overage.models.call_log import APICallLog
from overage.models.user import User
from typing import Any, Literal
```

### 16.4 No Hardcoded URLs or Values

```python
# WRONG
response = await client.post("https://api.openai.com/v1/chat/completions", ...)
THRESHOLD = 0.85

# CORRECT
from overage.config import settings
from overage.constants import ESTIMATION_CONFIDENCE_THRESHOLD

response = await client.post(f"{settings.openai_base_url}/chat/completions", ...)
if confidence > ESTIMATION_CONFIDENCE_THRESHOLD:
    ...
```

### 16.5 No Synchronous HTTP in Async Context

```python
# WRONG — blocks the event loop
import requests
async def fetch_data():
    response = requests.get("https://api.example.com/data")

# CORRECT
import httpx
async def fetch_data(client: httpx.AsyncClient):
    response = await client.get("https://api.example.com/data")
```

### 16.6 No Raw SQL

```python
# WRONG — SQL injection risk, unmaintainable
await session.execute(f"SELECT * FROM users WHERE email = '{email}'")

# CORRECT
from sqlalchemy import select
stmt = select(User).where(User.email == email)
result = await session.execute(stmt)
```

### 16.7 No Mutable Default Arguments

```python
# WRONG — the list is shared across all calls
def process_items(items: list[str] = []):
    items.append("new")
    return items

# CORRECT
def process_items(items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append("new")
    return items
```

### 16.8 No Global State

```python
# WRONG — global mutable state
db_connection = None

def get_db():
    global db_connection
    if db_connection is None:
        db_connection = connect()
    return db_connection

# CORRECT — use FastAPI dependency injection
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

@router.get("/calls")
async def list_calls(session: Annotated[AsyncSession, Depends(get_db_session)]):
    ...
```

### 16.9 No Deep Nesting

```python
# WRONG — 3+ levels of try/except
try:
    try:
        try:
            result = await process(data)
        except ValueError:
            ...
    except TypeError:
        ...
except RuntimeError:
    ...

# CORRECT — extract into functions
async def safe_process(data: dict) -> Result:
    try:
        return await process(data)
    except (ValueError, TypeError) as exc:
        raise ProcessingError(str(exc)) from exc
```

### 16.10 No Long Functions (>50 Lines)

```python
# WRONG — 80-line monolithic function
async def handle_proxy_request(...):
    # 80 lines of validation, forwarding, extraction, storage, logging...

# CORRECT — extract into focused helpers
async def handle_proxy_request(...):
    validated = validate_proxy_request(request_data)
    response = await forward_to_provider(client, provider, validated, api_key)
    usage = provider.extract_usage(response)
    await schedule_estimation(call_id, usage)
    return build_proxy_response(response)
```

### 16.11 No Long Files (>400 Lines)

If a file exceeds 400 lines, split it into focused modules. Example:

```
# WRONG: one massive estimation.py (600 lines)

# CORRECT: split into focused modules
estimation/
├── __init__.py
├── palace.py      # PALACE model inference (~100 lines)
├── timing.py      # Timing analysis (~80 lines)
├── aggregator.py  # Signal combination (~120 lines)
└── domain.py      # Domain classification (~60 lines)
```

### 16.12 No Uncommitted Migrations

```bash
# WRONG: change a model, push code, forget migration
# The database schema is now out of sync

# CORRECT: always generate + commit migration
# 1. Change model
# 2. alembic revision --autogenerate -m "description"
# 3. Review generated migration
# 4. alembic upgrade head (test locally)
# 5. git add alembic/versions/
# 6. git commit
```

### 16.13 No Tests Without Assertions

```python
# WRONG — this test always passes
def test_process_data():
    result = process_data({"key": "value"})
    # No assert!

# CORRECT
def test_process_data_valid_input_returns_expected_output():
    result = process_data({"key": "value"})
    assert result.status == "success"
    assert result.key == "value"
```

### 16.14 No Magic Numbers

```python
# WRONG
if discrepancy > 0.15:
    send_alert(...)
if len(calls) > 100:
    paginate(...)

# CORRECT
from overage.constants import DISCREPANCY_ALERT_THRESHOLD, DEFAULT_PAGE_SIZE

if discrepancy > DISCREPANCY_ALERT_THRESHOLD:
    send_alert(...)
if len(calls) > DEFAULT_PAGE_SIZE:
    paginate(...)
```

### 16.15 No String Concatenation for SQL

```python
# WRONG — SQL injection vulnerability
query = "SELECT * FROM users WHERE id = " + str(user_id)
await session.execute(text(query))

# CORRECT — parameterized query
stmt = select(User).where(User.id == user_id)
await session.execute(stmt)

# Also CORRECT if you must use text()
await session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})
```

---

## APPENDIX: Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│                    OVERAGE QUICK REF                     │
├─────────────────────────────────────────────────────────┤
│ Run proxy:          make run                            │
│ Run dashboard:      make run-dashboard                  │
│ Run all checks:     make check                          │
│ Run tests:          make test                           │
│ Format code:        make format                         │
│ Generate migration: make migration                      │
│ Apply migrations:   make migrate                        │
│                                                         │
│ NAMING:                                                 │
│   Files/funcs/vars: snake_case                          │
│   Classes:          PascalCase                          │
│   Constants:        SCREAMING_SNAKE_CASE                │
│   Tests:            test_<func>_<scenario>_<expected>   │
│                                                         │
│ EVERY FUNCTION MUST HAVE:                               │
│   ✅ Type annotations (all params + return)             │
│   ✅ Google-style docstring                             │
│   ✅ Structured logging (structlog, not print)          │
│   ✅ Specific exception handling (not bare except)      │
│                                                         │
│ BEFORE EVERY PUSH:                                      │
│   make lint && make typecheck && make test              │
└─────────────────────────────────────────────────────────┘
```
