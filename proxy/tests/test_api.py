"""Integration tests for the Overage API endpoints.

Tests the full request lifecycle including auth, database, and response format.
Reference: INSTRUCTIONS.md Section 8 (Testing Standards).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    import httpx

    from proxy.storage.models import APICallLog, DiscrepancyAlert, EstimationResult


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

    @pytest.mark.asyncio
    async def test_health_echoes_x_request_id_header(self, client: httpx.AsyncClient) -> None:
        """Middleware returns a UUID4 X-Request-ID on every response (Phase 0.3)."""
        response = await client.get("/health")
        assert response.status_code == 200
        raw = response.headers.get("X-Request-ID")
        assert raw is not None
        parsed = uuid.UUID(raw)
        assert parsed.version == 4

    @pytest.mark.asyncio
    async def test_health_echoes_client_x_request_id(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        """Middleware echoes a client-provided X-Request-ID when present."""
        client_rid = "a0a0a0a0-aaaa-4444-8888-bbbbbbbbbbbb"
        response = await client.get("/health", headers={"X-Request-ID": client_rid})
        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == client_rid


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
        assert "api_key" in data
        assert str(data["api_key"]).startswith("ovg_live_")

    @pytest.mark.asyncio
    async def test_post_apikey_requires_auth(self, client: httpx.AsyncClient) -> None:
        """POST /v1/auth/apikey without X-API-Key returns 401."""
        response = await client.post("/v1/auth/apikey", json={"name": "extra"})
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_post_apikey_returns_new_key(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """POST /v1/auth/apikey returns a new raw key once (Story 7)."""
        response = await client.post(
            "/v1/auth/apikey",
            headers={"X-API-Key": test_api_key},
            json={"name": "ci second key"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "ci second key"
        assert data["key"].startswith("ovg_live_")
        assert "created_at" in data

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
        header_rid = response.headers.get("X-Request-ID")
        body_rid = response.json().get("request_id")
        assert header_rid is not None
        assert body_rid is not None
        assert header_rid == body_rid

    @pytest.mark.asyncio
    async def test_list_calls_unknown_api_key_returns_401(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        """GET /v1/calls with a non-empty key not in the DB returns 401 (Phase 0.6)."""
        response = await client.get(
            "/v1/calls",
            headers={
                "X-API-Key": "ovg_live_notindb_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            },
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_calls_401_matches_x_request_id_header_and_body(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        """Auth errors echo the same request_id in JSON and X-Request-ID (middleware wiring)."""
        response = await client.get(
            "/v1/calls",
            headers={
                "X-API-Key": "ovg_live_notindb_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
            },
        )
        assert response.status_code == 401
        header_rid = response.headers.get("X-Request-ID")
        body_rid = response.json().get("request_id")
        assert header_rid is not None
        assert body_rid is not None
        assert header_rid == body_rid
        assert uuid.UUID(str(body_rid)).version == 4

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
        assert call["estimated_reasoning_tokens"] is None
        assert call["discrepancy_pct"] is None

    @pytest.mark.asyncio
    async def test_list_calls_includes_estimation_summary_when_present(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        sample_call_log: APICallLog,
        sample_estimation: EstimationResult,
        db_session: Any,
    ) -> None:
        """GET /v1/calls includes estimated tokens and discrepancy when estimation exists."""
        await db_session.commit()

        response = await client.get(
            "/v1/calls",
            headers={"X-API-Key": test_api_key},
        )

        assert response.status_code == 200
        call = response.json()["calls"][0]
        assert call["estimated_reasoning_tokens"] == sample_estimation.combined_estimated_tokens
        assert call["discrepancy_pct"] == round(sample_estimation.discrepancy_pct, 4)
        assert call["timing_r_squared"] == sample_estimation.timing_r_squared
        assert call["signals_agree"] is sample_estimation.signals_agree

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
    async def test_summary_group_by_provider_returns_overall_and_groups(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        sample_call_log: APICallLog,
        sample_estimation: EstimationResult,
        db_session: Any,
    ) -> None:
        """group_by=provider returns SummaryWithGroups shape."""
        await db_session.commit()

        response = await client.get(
            "/v1/summary",
            headers={"X-API-Key": test_api_key},
            params={"group_by": "provider"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "overall" in data
        assert "groups" in data
        assert data["overall"]["total_calls"] >= 1
        assert len(data["groups"]) >= 1
        assert data["groups"][0]["group_key"] == "openai"
        assert data["groups"][0]["low_confidence"] is True

    @pytest.mark.asyncio
    async def test_summary_invalid_group_by_returns_422(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """Invalid group_by returns 422."""
        response = await client.get(
            "/v1/summary",
            headers={"X-API-Key": test_api_key},
            params={"group_by": "nope"},
        )
        assert response.status_code == 422

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


class TestAlertsEndpoint:
    """Tests for GET /v1/alerts."""

    @pytest.mark.asyncio
    async def test_list_alerts_requires_auth(self, client: httpx.AsyncClient) -> None:
        """GET /v1/alerts without API key returns 401."""
        response = await client.get("/v1/alerts")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_alerts_returns_empty_for_new_user(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """No alerts stored yet returns empty list."""
        response = await client.get(
            "/v1/alerts",
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["alerts"] == []
        assert data["total"] == 0


class TestAcknowledgeAlert:
    """Tests for POST /v1/alerts/{id}/acknowledge."""

    @pytest.mark.asyncio
    async def test_acknowledge_requires_auth(self, client: httpx.AsyncClient) -> None:
        """Missing API key returns 401."""
        response = await client.post("/v1/alerts/1/acknowledge")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_acknowledge_unknown_returns_404(
        self, client: httpx.AsyncClient, test_api_key: str, db_session: Any
    ) -> None:
        """Non-existent alert id returns 404."""
        await db_session.commit()
        response = await client.post(
            "/v1/alerts/99999/acknowledge",
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_acknowledge_other_users_alert_returns_404(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        stranger_discrepancy_alert: DiscrepancyAlert,
        db_session: Any,
    ) -> None:
        """Cannot acknowledge another user's alert."""
        await db_session.commit()
        response = await client.post(
            f"/v1/alerts/{stranger_discrepancy_alert.id}/acknowledge",
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_acknowledge_active_sets_status_and_is_idempotent(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        sample_discrepancy_alert: DiscrepancyAlert,
        db_session: Any,
    ) -> None:
        """Active alert becomes acknowledged; repeat POST is idempotent."""
        await db_session.commit()
        aid = sample_discrepancy_alert.id
        r1 = await client.post(
            f"/v1/alerts/{aid}/acknowledge",
            headers={"X-API-Key": test_api_key},
        )
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["alert_status"] == "acknowledged"
        assert d1["acknowledged_at"] is not None

        r2 = await client.post(
            f"/v1/alerts/{aid}/acknowledge",
            headers={"X-API-Key": test_api_key},
        )
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["alert_status"] == "acknowledged"
        # JSON may emit trailing Z on first response only depending on serialization path.
        assert d2["acknowledged_at"] is not None
        assert d2["acknowledged_at"].replace("Z", "") == d1["acknowledged_at"].replace("Z", "")


class TestReportEndpoint:
    """Tests for GET /v1/report (PDF audit)."""

    @pytest.mark.asyncio
    async def test_report_requires_auth(self, client: httpx.AsyncClient) -> None:
        """Missing API key returns 401."""
        response = await client.get(
            "/v1/report",
            params={"start_date": "2026-01-01", "end_date": "2026-01-31"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_report_rejects_inverted_date_range(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """end_date before start_date yields 422."""
        response = await client.get(
            "/v1/report",
            headers={"X-API-Key": test_api_key},
            params={"start_date": "2026-02-01", "end_date": "2026-01-01"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_report_rejects_range_over_one_year(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """Range wider than 366 days yields 422."""
        response = await client.get(
            "/v1/report",
            headers={"X-API-Key": test_api_key},
            params={"start_date": "2024-01-01", "end_date": "2025-12-31"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_report_returns_pdf_bytes(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        sample_call_log: Any,
        sample_estimation: Any,
        db_session: Any,
    ) -> None:
        """Returns application/pdf with PDF magic bytes and attachment disposition."""
        pytest.importorskip("fpdf")
        await db_session.commit()
        from datetime import UTC, datetime, timedelta

        end_d = datetime.now(tz=UTC).date()
        start_d = end_d - timedelta(days=30)
        response = await client.get(
            "/v1/report",
            headers={"X-API-Key": test_api_key},
            params={"start_date": str(start_d), "end_date": str(end_d)},
        )
        assert response.status_code == 200
        ct = response.headers.get("content-type", "")
        assert "application/pdf" in ct
        assert response.content[:4] == b"%PDF"
        cd = response.headers.get("content-disposition", "")
        assert "attachment" in cd.lower()


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
