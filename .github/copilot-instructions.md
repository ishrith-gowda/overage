# Copilot Instructions — Overage

> This file configures GitHub Copilot's behavior for the Overage repository.
> Copilot reads this automatically for repo-level context.

## Project Context

Overage is a FastAPI reverse proxy that audits hidden LLM reasoning token billing. It sits between enterprise apps and LLM providers (OpenAI, Anthropic, Gemini), intercepts API calls, and independently verifies provider-reported reasoning token counts using two signals: (1) PALACE model inference (LoRA-fine-tuned Qwen2.5-1.5B) and (2) response timing analysis. The proxy adds <10ms to the critical path; estimation runs asynchronously via background tasks. The tech stack is Python 3.12, FastAPI, httpx, SQLAlchemy 2.0 async, Alembic, Pydantic v2, structlog, pytest, and Streamlit for the dashboard. All code must have full type annotations, Google-style docstrings, and structured logging via structlog. Never use print(), bare except, star imports, synchronous HTTP in async functions, raw SQL strings, or mutable default arguments.

---

## KEY PATTERNS TO ALWAYS FOLLOW

### Pattern 1: New API Endpoint

When creating any new FastAPI endpoint, always follow this exact structure:

```python
"""Module docstring describing the endpoint group."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from overage.dependencies import get_current_user, get_db_session
from overage.exceptions import ValidationError
from overage.models.user import User
from overage.schemas.common import ErrorResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/resource", tags=["resource"])


@router.get(
    "",
    response_model=ResourceListResponse,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def list_resources(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200, description="Results per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> ResourceListResponse:
    """List resources for the authenticated user.

    Args:
        session: Database session (injected).
        current_user: Authenticated user (injected).
        limit: Maximum results to return.
        offset: Pagination offset.

    Returns:
        Paginated list of resources.
    """
    log = logger.bind(user_id=current_user.id)
    log.info("list_resources_requested")

    stmt = (
        select(Resource)
        .where(Resource.user_id == current_user.id)
        .order_by(Resource.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    items = list(result.scalars().all())

    log.info("list_resources_complete", count=len(items))
    return ResourceListResponse(items=items, total=len(items), limit=limit, offset=offset)
```

### Pattern 2: New LLM Provider

When implementing a new provider adapter:

```python
# src/overage/providers/newprovider.py
"""NewProvider adapter."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from overage.exceptions import ProviderAPIError, ProviderTimeoutError
from overage.providers.base import BaseProvider

logger = structlog.get_logger(__name__)


class NewProvider(BaseProvider):
    """Adapter for the NewProvider API."""

    def __init__(self, base_url: str = "https://api.newprovider.com/v1") -> None:
        self._base_url = base_url

    @property
    def name(self) -> str:
        return "newprovider"

    @property
    def base_url(self) -> str:
        return self._base_url

    async def forward_request(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        api_key: str,
    ) -> dict[str, Any]:
        """Forward request to NewProvider."""
        url = f"{self.base_url}/completions"
        log = logger.bind(provider=self.name, model=payload.get("model"))

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
            raise ProviderTimeoutError(provider=self.name, timeout_seconds=300.0) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderAPIError(
                provider=self.name,
                status_code=exc.response.status_code,
                detail=exc.response.text[:500],
            ) from exc

    def extract_usage(self, response_data: dict[str, Any]) -> dict[str, int]:
        """Extract token usage from NewProvider response."""
        usage = response_data.get("usage")
        if usage is None:
            raise ProviderAPIError(
                provider=self.name, status_code=200, detail="Missing 'usage' field"
            )
        return {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "reasoning_tokens": usage.get("thinking_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    def get_model_from_response(self, response_data: dict[str, Any]) -> str:
        """Extract model name from response."""
        return response_data.get("model", "unknown")
```

Then register in `src/overage/providers/registry.py`:

```python
from overage.providers.newprovider import NewProvider
_PROVIDERS["newprovider"] = NewProvider
```

### Pattern 3: Database Query

Always use async SQLAlchemy 2.0 with session dependency injection:

```python
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

async def get_discrepancy_summary(
    session: AsyncSession,
    user_id: int,
    days: int = 30,
) -> dict[str, Any]:
    """Get aggregate discrepancy stats for the last N days.

    Args:
        session: Async database session.
        user_id: The user's ID.
        days: Lookback window in days.

    Returns:
        Summary dict with total_calls, avg_discrepancy_pct, total_dollar_impact.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(
            func.count(APICallLog.id).label("total_calls"),
            func.avg(EstimationResult.discrepancy_pct).label("avg_discrepancy_pct"),
            func.sum(EstimationResult.dollar_impact).label("total_dollar_impact"),
        )
        .join(EstimationResult, APICallLog.id == EstimationResult.call_id)
        .where(APICallLog.user_id == user_id)
        .where(APICallLog.timestamp >= cutoff)
    )
    result = await session.execute(stmt)
    row = result.one()
    return {
        "total_calls": row.total_calls or 0,
        "avg_discrepancy_pct": float(row.avg_discrepancy_pct or 0),
        "total_dollar_impact": float(row.total_dollar_impact or 0),
    }
```

### Pattern 4: Structured Logging

Always use structlog with context binding:

```python
import structlog

logger = structlog.get_logger(__name__)

async def process_call(call_id: int, request_id: str) -> None:
    """Process an API call."""
    log = logger.bind(call_id=call_id, request_id=request_id)
    log.info("processing_started")

    try:
        result = await run_estimation(call_id)
        log.info(
            "processing_complete",
            estimated_tokens=result.estimated_tokens,
            discrepancy_pct=result.discrepancy_pct,
        )
    except EstimationError as exc:
        log.error("processing_failed", error=str(exc), error_type=type(exc).__name__)
        raise
```

### Pattern 5: Error Handling

Always catch specific exceptions, log, and re-raise as typed errors:

```python
from overage.exceptions import (
    OverageError,
    ProviderAPIError,
    ProviderTimeoutError,
    EstimationError,
)

async def forward_and_estimate(
    client: httpx.AsyncClient,
    provider: BaseProvider,
    payload: dict[str, Any],
    api_key: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Forward request and extract usage.

    Returns:
        Tuple of (response_data, usage_data).

    Raises:
        ProviderTimeoutError: Provider did not respond in time.
        ProviderAPIError: Provider returned an error.
    """
    response_data = await provider.forward_request(client, payload, api_key)
    usage = provider.extract_usage(response_data)
    return response_data, usage
```

### Pattern 6: Writing Tests

Always follow this test structure:

```python
"""Tests for module_name."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from overage.exceptions import ProviderAPIError


@pytest.fixture
def sample_response() -> dict[str, Any]:
    """Sample provider response for testing."""
    return {
        "model": "o3",
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 500,
            "total_tokens": 600,
            "completion_tokens_details": {"reasoning_tokens": 400},
        },
    }


class TestExtractUsage:
    """Tests for usage extraction."""

    def test_extract_usage_with_reasoning_tokens_returns_correct_count(
        self,
        openai_provider: OpenAIProvider,
        sample_response: dict[str, Any],
    ) -> None:
        """Extract reasoning tokens from a valid response."""
        usage = openai_provider.extract_usage(sample_response)

        assert usage["reasoning_tokens"] == 400
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 500

    def test_extract_usage_missing_usage_raises_error(
        self,
        openai_provider: OpenAIProvider,
    ) -> None:
        """Raise ProviderAPIError when usage field is missing."""
        with pytest.raises(ProviderAPIError, match="Missing 'usage'"):
            openai_provider.extract_usage({"model": "o3", "choices": []})

    @pytest.mark.asyncio
    async def test_forward_request_timeout_raises_timeout_error(
        self,
        openai_provider: OpenAIProvider,
    ) -> None:
        """Raise ProviderTimeoutError on timeout."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")

        with pytest.raises(ProviderTimeoutError):
            await openai_provider.forward_request(mock_client, {}, "key")
```

### Pattern 7: Async Functions with httpx

```python
import httpx

async def fetch_model_info(
    client: httpx.AsyncClient,
    model_id: str,
) -> dict[str, Any]:
    """Fetch model metadata.

    Args:
        client: Shared async HTTP client.
        model_id: The model identifier.

    Returns:
        Model metadata dictionary.

    Raises:
        ProviderAPIError: If the request fails.
    """
    try:
        response = await client.get(
            f"https://api.openai.com/v1/models/{model_id}",
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise ProviderAPIError(
            provider="openai",
            status_code=exc.response.status_code,
            detail=exc.response.text[:500],
        ) from exc
```

### Pattern 8: Config Variable

Add new configuration to `src/overage/config.py`:

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Existing...
    new_variable: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Description of the new variable",
    )
    new_url: str = Field(
        default="https://api.example.com",
        pattern=r"^https?://",
        description="Base URL for the new service",
    )
    new_secret: str = Field(
        default="",
        description="API key for new service (set via env var)",
    )

settings = Settings()
```

Then add to `.env.example`:

```
NEW_VARIABLE=100
NEW_URL=https://api.example.com
NEW_SECRET=
```

### Pattern 9: Pydantic Request/Response Model

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CallListRequest(BaseModel):
    """Query parameters for listing API calls."""

    provider: str | None = Field(None, description="Filter by provider name")
    model: str | None = Field(None, description="Filter by model name")
    limit: int = Field(50, ge=1, le=200, description="Results per page")
    offset: int = Field(0, ge=0, description="Pagination offset")


class CallSummary(BaseModel):
    """Summary of a single API call."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    model: str
    reported_reasoning_tokens: int
    estimated_reasoning_tokens: int | None = None
    discrepancy_pct: float | None = None
    timestamp: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "provider": "openai",
                "model": "o3",
                "reported_reasoning_tokens": 10000,
                "estimated_reasoning_tokens": 8200,
                "discrepancy_pct": 21.95,
                "timestamp": "2026-03-31T12:00:00Z",
            }
        }
    )


class CallListResponse(BaseModel):
    """Paginated list of API calls."""

    calls: list[CallSummary]
    total: int
    limit: int
    offset: int
```

### Pattern 10: FastAPI Dependency Injection

```python
# src/overage/dependencies.py
from __future__ import annotations

from typing import Annotated, AsyncGenerator

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from overage.config import settings
from overage.exceptions import AuthenticationError, RateLimitExceededError
from overage.models.database import async_session_factory
from overage.models.user import User
from overage.utils.hashing import hash_api_key


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    x_api_key: Annotated[str, Header(description="Overage API key")],
) -> User:
    """Authenticate and return the current user from API key.

    Args:
        session: Database session (injected).
        x_api_key: API key from request header.

    Returns:
        The authenticated User.

    Raises:
        AuthenticationError: If the API key is invalid.
    """
    from sqlalchemy import select
    from overage.models.api_key import APIKey

    key_hash = hash_api_key(x_api_key)
    stmt = (
        select(User)
        .join(APIKey, User.id == APIKey.user_id)
        .where(APIKey.key_hash == key_hash, APIKey.is_active.is_(True))
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError()
    return user
```

### Pattern 11: Streaming SSE Response

```python
from fastapi.responses import StreamingResponse

@router.post("/v1/proxy/{provider}")
async def proxy_request(
    provider: str,
    request: Request,
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StreamingResponse:
    """Proxy an LLM API call, recording timing and usage."""
    body = await request.json()
    provider_impl = get_provider(provider)
    api_key = get_provider_api_key(provider, current_user)
    start_time = time.perf_counter()

    if body.get("stream", False):
        accumulated_chunks: list[bytes] = []

        async def stream_with_recording() -> AsyncGenerator[bytes, None]:
            async with client.stream(
                "POST",
                f"{provider_impl.base_url}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=300.0,
            ) as response:
                async for chunk in response.aiter_bytes():
                    accumulated_chunks.append(chunk)
                    yield chunk

            # After streaming completes, process in background
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            background_tasks.add_task(
                process_streamed_response,
                chunks=accumulated_chunks,
                provider=provider,
                elapsed_ms=elapsed_ms,
                user_id=current_user.id,
            )

        return StreamingResponse(
            stream_with_recording(),
            media_type="text/event-stream",
        )
    else:
        response_data = await provider_impl.forward_request(client, body, api_key)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        usage = provider_impl.extract_usage(response_data)
        background_tasks.add_task(
            process_call, response_data, usage, elapsed_ms, current_user.id
        )
        return JSONResponse(content=response_data)
```

### Pattern 12: Background Task

```python
from fastapi import BackgroundTasks

@router.post("/v1/proxy/{provider}")
async def proxy_request(
    provider: str,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """Proxy request with async estimation."""
    # ... forward to provider ...

    # Schedule async estimation (does NOT block the response)
    background_tasks.add_task(
        run_estimation_pipeline,
        call_id=call_log.id,
        prompt=prompt_text,
        answer=answer_text,
        response_time_ms=elapsed_ms,
        reported_tokens=usage["reasoning_tokens"],
    )

    return JSONResponse(content=response_data)


async def run_estimation_pipeline(
    call_id: int,
    prompt: str,
    answer: str,
    response_time_ms: float,
    reported_tokens: int,
) -> None:
    """Run PALACE + timing estimation asynchronously.

    This runs in the background after the proxy response is sent.
    """
    log = logger.bind(call_id=call_id)
    log.info("estimation_pipeline_started")

    async with async_session_factory() as session:
        palace_result = await run_palace_inference(prompt, answer)
        timing_result = estimate_from_timing(response_time_ms, model="o3")
        aggregated = aggregate_signals(palace_result, timing_result, reported_tokens)

        estimation = EstimationResult(call_id=call_id, **aggregated)
        session.add(estimation)
        await session.commit()

    log.info("estimation_pipeline_complete", discrepancy_pct=aggregated["discrepancy_pct"])
```

### Pattern 13: Alembic Migration

```bash
# 1. Modify a model (e.g., add a column)
# 2. Generate the migration
alembic revision --autogenerate -m "add confidence_score to estimation_results"

# 3. Review the generated file in alembic/versions/
# 4. Apply
alembic upgrade head
```

### Pattern 14: Streamlit Dashboard Panel

```python
# src/dashboard/pages/overview.py
import streamlit as st
import plotly.express as px
import pandas as pd
from overage.models.database import get_sync_engine

st.set_page_config(page_title="Overage Dashboard", layout="wide")
st.title("Overage — Reasoning Token Audit")

engine = get_sync_engine()


@st.cache_data(ttl=60)
def load_summary_data() -> pd.DataFrame:
    """Load aggregate discrepancy data."""
    query = """
        SELECT date(timestamp) as date, provider, model,
               AVG(discrepancy_pct) as avg_discrepancy,
               SUM(dollar_impact) as total_impact,
               COUNT(*) as call_count
        FROM api_call_logs
        JOIN estimation_results ON api_call_logs.id = estimation_results.call_id
        GROUP BY date(timestamp), provider, model
        ORDER BY date DESC
    """
    return pd.read_sql(query, engine)


data = load_summary_data()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Calls Audited", f"{data['call_count'].sum():,}")
with col2:
    st.metric("Avg Discrepancy", f"{data['avg_discrepancy'].mean():.1f}%")
with col3:
    st.metric("Estimated Overcharge", f"${data['total_impact'].sum():,.2f}")

fig = px.line(data, x="date", y="avg_discrepancy", color="provider", title="Discrepancy Over Time")
st.plotly_chart(fig, use_container_width=True)
```

### Pattern 15: CLI Script

```python
#!/usr/bin/env python3
"""Generate synthetic demo data for Overage demos."""

from __future__ import annotations

import argparse
import asyncio
import sys

import structlog

logger = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Generate demo data for Overage")
    parser.add_argument("--calls", type=int, default=500, help="Number of calls to generate")
    parser.add_argument("--days", type=int, default=30, help="Days of history to simulate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    return parser.parse_args()


async def main() -> int:
    """Generate demo data."""
    args = parse_args()
    logger.info("generating_demo_data", calls=args.calls, days=args.days)
    # ... generation logic ...
    logger.info("demo_data_complete", calls_generated=args.calls)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

---

## KEY ANTI-PATTERNS TO NEVER GENERATE

### Never: Synchronous HTTP in async context

```python
# WRONG
import requests
async def fetch():
    return requests.get(url)  # Blocks event loop

# CORRECT
import httpx
async def fetch(client: httpx.AsyncClient):
    return await client.get(url)
```

### Never: Bare except

```python
# WRONG
try:
    result = await process()
except:
    pass

# CORRECT
try:
    result = await process()
except SpecificError as exc:
    logger.error("process_failed", error=str(exc))
    raise
```

### Never: print() statements

```python
# WRONG
print(f"Debug: {value}")

# CORRECT
logger.debug("debug_value", value=value)
```

### Never: Hardcoded API keys or URLs

```python
# WRONG
api_key = "sk-abc123"
url = "https://api.openai.com/v1/chat/completions"

# CORRECT
from overage.config import settings
api_key = settings.openai_api_key
url = f"{settings.openai_base_url}/chat/completions"
```

### Never: Raw SQL strings

```python
# WRONG
await session.execute(f"SELECT * FROM users WHERE id = {user_id}")

# CORRECT
stmt = select(User).where(User.id == user_id)
await session.execute(stmt)
```

### Never: Functions without type annotations

```python
# WRONG
def compute_discrepancy(reported, estimated):
    return (reported - estimated) / estimated * 100

# CORRECT
def compute_discrepancy(reported: int, estimated: int) -> float:
    """Compute discrepancy percentage between reported and estimated tokens."""
    return (reported - estimated) / estimated * 100
```

### Never: Functions without docstrings

```python
# WRONG
async def process_call(call_id: int) -> None:
    result = await estimate(call_id)

# CORRECT
async def process_call(call_id: int) -> None:
    """Process a single API call through the estimation pipeline.

    Args:
        call_id: The call log ID to process.
    """
    result = await estimate(call_id)
```

### Never: Tests without assertions

```python
# WRONG
def test_something():
    process_data({"key": "value"})

# CORRECT
def test_process_data_returns_expected():
    result = process_data({"key": "value"})
    assert result.status == "success"
```

### Never: Star imports

```python
# WRONG
from overage.models import *

# CORRECT
from overage.models.call_log import APICallLog
from overage.models.user import User
```

### Never: Mutable default arguments

```python
# WRONG
def process(items: list[str] = []):
    items.append("new")

# CORRECT
def process(items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append("new")
    return items
```

---

## IMPORT ORDERING

```python
# 1. Standard library
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Annotated

# 2. Third-party
import httpx
import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 3. First-party (overage)
from overage.config import settings
from overage.constants import DEFAULT_RATE_LIMIT_PER_MINUTE
from overage.dependencies import get_current_user, get_db_session
from overage.exceptions import ProviderAPIError, ValidationError
from overage.models.call_log import APICallLog
from overage.schemas.calls import CallListResponse
```

Ruff enforces this automatically via `I` (isort) rules.

---

## TYPE ANNOTATION RULES

```python
# Use built-in generics (3.10+)
items: list[str]                    # Not List[str]
mapping: dict[str, int]             # Not Dict[str, int]
optional: str | None                # Not Optional[str]

# Complex nested types
records: list[dict[str, Any]]
callback: Callable[[str, int], Awaitable[bool]]
generator: AsyncGenerator[bytes, None]

# TypedDict for structured data
class UsageData(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    reasoning_tokens: int

# Literal for constrained strings
provider: Literal["openai", "anthropic", "gemini"]
```

---

## RESPONSE FORMAT TEMPLATE

### Success Response

```json
{
  "calls": [...],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

### Error Response

```json
{
  "error": "Rate limit exceeded: 100 requests per 60s",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "detail": null,
  "request_id": "req_abc123"
}
```

Always use `ErrorResponse` from `overage.schemas.common` for error responses. Always include `request_id` when available.

---

## GIT COMMIT RULES

All commit messages must follow these rules exactly:

1. **All lowercase** — the entire message must be lowercase
2. **Single line only** — never use multi-line commit messages
3. **No trailers** — never add `Co-authored-by:`, `Made-with:`, `Signed-off-by:`, or any trailer
4. **One logical unit** — each commit covers exactly one change; many small commits are preferred
5. **Conventional prefix** — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `ci:`, `chore:`

Good: `feat: add openai provider adapter with usage extraction`
Bad: `Feat: Add OpenAI Provider` (uppercase, vague)
