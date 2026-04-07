"""Integration tests for the Overage API endpoints.

Tests the full request lifecycle including auth, database, and response format.
Reference: INSTRUCTIONS.md Section 8 (Testing Standards).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    import httpx

    from proxy.storage.models import APICallLog, EstimationResult


class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.asyncio
    async def test_health_returns_200_and_status(self, client: httpx.AsyncClient) -> None:
        """Health check returns 200 with status information."""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert "version" in data
        assert "uptime_seconds" in data
        assert "db_connected" in data
        assert "providers" in data

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client: httpx.AsyncClient) -> None:
        """Health endpoint does not require an API key."""
        response = await client.get("/health")
        assert response.status_code == 200


class TestAuthEndpoints:
    """Tests for auth registration and API key generation."""

    @pytest.mark.asyncio
    async def test_register_creates_user(self, client: httpx.AsyncClient) -> None:
        """POST /v1/auth/register creates a new user."""
        response = await client.post(
            "/v1/auth/register",
            json={"email": "new@test.com", "name": "New User", "password": "securepass123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new@test.com"
        assert data["name"] == "New User"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, client: httpx.AsyncClient) -> None:
        """Registering with an existing email returns 409."""
        payload = {"email": "dupe@test.com", "name": "User 1", "password": "securepass123"}
        await client.post("/v1/auth/register", json=payload)
        response = await client.post("/v1/auth/register", json=payload)

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_short_password_returns_422(self, client: httpx.AsyncClient) -> None:
        """Password shorter than 8 characters returns 422."""
        response = await client.post(
            "/v1/auth/register",
            json={"email": "short@test.com", "name": "User", "password": "short"},
        )

        assert response.status_code == 422


class TestCallsEndpoints:
    """Tests for GET /v1/calls and GET /v1/calls/{id}."""

    @pytest.mark.asyncio
    async def test_list_calls_requires_auth(self, client: httpx.AsyncClient) -> None:
        """GET /v1/calls without API key returns 401."""
        response = await client.get("/v1/calls")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_calls_returns_empty_for_new_user(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """GET /v1/calls returns empty list for user with no calls."""
        response = await client.get(
            "/v1/calls",
            headers={"X-API-Key": test_api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["calls"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_calls_returns_user_calls(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        sample_call_log: APICallLog,
        db_session: Any,
    ) -> None:
        """GET /v1/calls returns calls belonging to the authenticated user."""
        # Commit the sample call so it's visible to the API
        await db_session.commit()

        response = await client.get(
            "/v1/calls",
            headers={"X-API-Key": test_api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        call = data["calls"][0]
        assert call["provider"] == "openai"
        assert call["model"] == "o3"
        assert call["reported_reasoning_tokens"] == 10000

    @pytest.mark.asyncio
    async def test_get_call_detail_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """GET /v1/calls/{id} returns 404 for nonexistent call."""
        response = await client.get(
            "/v1/calls/99999",
            headers={"X-API-Key": test_api_key},
        )

        assert response.status_code == 404


class TestSummaryEndpoint:
    """Tests for GET /v1/summary."""

    @pytest.mark.asyncio
    async def test_summary_returns_zeros_for_new_user(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """Summary returns zero values when no calls exist."""
        response = await client.get(
            "/v1/summary",
            headers={"X-API-Key": test_api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_calls"] == 0
        assert data["total_dollar_impact"] == 0.0

    @pytest.mark.asyncio
    async def test_summary_with_data_returns_aggregates(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        sample_call_log: APICallLog,
        sample_estimation: EstimationResult,
        db_session: Any,
    ) -> None:
        """Summary returns aggregate statistics when calls and estimations exist."""
        await db_session.commit()

        response = await client.get(
            "/v1/summary",
            headers={"X-API-Key": test_api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_calls"] >= 1
        assert data["total_reported_reasoning_tokens"] > 0


class TestTimeseriesEndpoint:
    """Tests for GET /v1/summary/timeseries."""

    @pytest.mark.asyncio
    async def test_timeseries_returns_data_structure(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """Timeseries endpoint returns the correct structure."""
        response = await client.get(
            "/v1/summary/timeseries",
            headers={"X-API-Key": test_api_key},
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "period" in data
        assert isinstance(data["data"], list)
