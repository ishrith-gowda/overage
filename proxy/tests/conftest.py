"""Shared test fixtures for the Overage proxy test suite.

Provides: test app, async client, in-memory database, mock responses, and factories.
Reference: INSTRUCTIONS.md Section 8 (Testing Standards).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from proxy.storage.models import (
    APICallLog,
    APIKey,
    Base,
    DiscrepancyAlert,
    EstimationResult,
    User,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI

# ---------------------------------------------------------------------------
# Environment overrides — set BEFORE importing app modules
# ---------------------------------------------------------------------------
os.environ["OVERAGE_ENV"] = "development"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"
os.environ["SENTRY_DSN"] = ""
os.environ["ESTIMATION_ENABLED"] = "false"
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["API_KEY_SECRET"] = "test-secret"
os.environ["LOG_LEVEL"] = "WARNING"


# ---------------------------------------------------------------------------
# Database fixtures — in-memory SQLite, isolated per test
# ---------------------------------------------------------------------------

_test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
)
_test_session_factory = async_sessionmaker(
    _test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database() -> AsyncGenerator[None, None]:
    """Create all tables before each test, drop after."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh async database session for each test."""
    async with _test_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# App and client fixtures
# ---------------------------------------------------------------------------


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Override the get_db dependency to use the test database."""
    async with _test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI app with overridden dependencies."""
    # Clear settings cache so test env vars are picked up
    from proxy.config import get_settings

    get_settings.cache_clear()

    from proxy.main import create_app
    from proxy.storage.database import get_db

    test_app = create_app()
    test_app.dependency_overrides[get_db] = _override_get_db
    return test_app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an httpx.AsyncClient bound to the test app."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Seed data fixtures
# ---------------------------------------------------------------------------

_TEST_RAW_KEY = "ovg_live_testkey1234567890abcdef1234567890abcdef1234567890abcdef1234"
_TEST_KEY_HASH = hashlib.sha256(_TEST_RAW_KEY.encode()).hexdigest()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user in the database."""
    user = User(
        email="test@overage.dev",
        name="Test User",
        password_hash=hashlib.sha256(b"testpassword").hexdigest(),
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def test_api_key(db_session: AsyncSession, test_user: User) -> str:
    """Create a test API key and return the raw key string."""
    api_key = APIKey(
        user_id=test_user.id,
        key_hash=_TEST_KEY_HASH,
        name="Test Key",
        is_active=True,
    )
    db_session.add(api_key)
    await db_session.commit()
    return _TEST_RAW_KEY


@pytest_asyncio.fixture
async def sample_call_log(db_session: AsyncSession, test_user: User) -> APICallLog:
    """Create a sample API call log record."""
    call = APICallLog(
        user_id=test_user.id,
        provider="openai",
        model="o3",
        prompt_hash="abc123def456",
        prompt_length_chars=500,
        answer_length_chars=1000,
        reported_input_tokens=100,
        reported_output_tokens=1500,
        reported_reasoning_tokens=10000,
        total_latency_ms=18500.0,
        ttft_ms=None,
        is_streaming=False,
        raw_usage_json=json.dumps(
            {
                "prompt_tokens": 100,
                "completion_tokens": 1500,
                "total_tokens": 1600,
                "completion_tokens_details": {"reasoning_tokens": 10000},
            }
        ),
        request_id="req_test_001",
    )
    db_session.add(call)
    await db_session.flush()
    return call


@pytest_asyncio.fixture
async def sample_estimation(
    db_session: AsyncSession, sample_call_log: APICallLog
) -> EstimationResult:
    """Create a sample estimation result linked to the sample call log."""
    estimation = EstimationResult(
        call_id=sample_call_log.id,
        palace_estimated_tokens=8200,
        palace_confidence_low=7800,
        palace_confidence_high=8600,
        palace_model_version="v0.1.0",
        timing_estimated_tokens=8525,
        timing_tps_used=55.0,
        timing_r_squared=0.992,
        combined_estimated_tokens=8300,
        discrepancy_pct=20.48,
        dollar_impact=0.102,
        signals_agree=True,
        domain_classification="math_reasoning",
    )
    db_session.add(estimation)
    await db_session.flush()
    return estimation


@pytest_asyncio.fixture
async def sample_discrepancy_alert(db_session: AsyncSession, test_user: User) -> DiscrepancyAlert:
    """Create an active discrepancy alert for the test user."""
    now = datetime.now(tz=UTC)
    alert = DiscrepancyAlert(
        user_id=test_user.id,
        window_start=now - timedelta(days=1),
        window_end=now,
        call_count=42,
        aggregate_discrepancy_pct=22.5,
        dollar_impact=12.34,
        confidence_level="medium",
        threshold_pct=15.0,
        alert_status="active",
    )
    db_session.add(alert)
    await db_session.flush()
    return alert


@pytest_asyncio.fixture
async def stranger_user(db_session: AsyncSession) -> User:
    """A second user (no API key fixture) for cross-tenant alert tests."""
    user = User(
        email="stranger@overage.dev",
        name="Stranger",
        password_hash=hashlib.sha256(b"other-password").hexdigest(),
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def stranger_discrepancy_alert(
    db_session: AsyncSession, stranger_user: User
) -> DiscrepancyAlert:
    """Active alert belonging to ``stranger_user`` (not ``test_api_key``'s user)."""
    now = datetime.now(tz=UTC)
    alert = DiscrepancyAlert(
        user_id=stranger_user.id,
        window_start=now - timedelta(days=2),
        window_end=now - timedelta(days=1),
        call_count=5,
        aggregate_discrepancy_pct=30.0,
        dollar_impact=1.0,
        confidence_level="low",
        threshold_pct=15.0,
        alert_status="active",
    )
    db_session.add(alert)
    await db_session.flush()
    return alert


# ---------------------------------------------------------------------------
# Mock response factories
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_openai_response() -> Any:
    """Factory for generating realistic OpenAI API responses."""

    def _factory(
        model: str = "o3",
        reasoning_tokens: int = 10000,
        prompt_tokens: int = 100,
        completion_tokens: int = 1500,
    ) -> dict[str, Any]:
        return {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Test answer."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "completion_tokens_details": {
                    "reasoning_tokens": reasoning_tokens,
                    "accepted_prediction_tokens": 0,
                    "rejected_prediction_tokens": 0,
                },
            },
        }

    return _factory


@pytest.fixture
def mock_anthropic_response() -> Any:
    """Factory for generating realistic Anthropic API responses."""

    def _factory(
        model: str = "claude-sonnet-4-20250514",
        thinking_tokens: int = 5000,
        input_tokens: int = 200,
        output_tokens: int = 800,
    ) -> dict[str, Any]:
        return {
            "id": "msg_test123",
            "type": "message",
            "model": model,
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Test answer."},
            ],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "thinking_tokens": thinking_tokens,
            },
        }

    return _factory
