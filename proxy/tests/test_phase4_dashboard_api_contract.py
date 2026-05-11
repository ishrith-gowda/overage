"""Phase 4 — JSON contracts required by ``dashboard/app.py`` (HTTP-level).

The Streamlit UI is not executed in CI; these tests pin the shapes and keys
the dashboard reads for KPIs, grouped summary bars, time-series charts, and
the active-alerts banner so API drift is caught before manual screenshot work.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

# Keys read by ``dashboard/app.py`` for KPI metrics (flat or nested under ``overall``).
_DASHBOARD_KPI_KEYS: frozenset[str] = frozenset(
    {
        "total_calls",
        "total_reported_reasoning_tokens",
        "total_estimated_reasoning_tokens",
        "aggregate_discrepancy_pct",
        "total_dollar_impact",
        "honoring_rate_pct",
        "avg_discrepancy_pct",
    }
)

# Group rows become a DataFrame then a Plotly bar chart (group_key, aggregate_discrepancy_pct, …).
_DASHBOARD_GROUP_KEYS: frozenset[str] = frozenset(
    {
        "group_key",
        "provider",
        "model",
        "call_count",
        "total_reported_reasoning_tokens",
        "total_estimated_reasoning_tokens",
        "aggregate_discrepancy_pct",
        "avg_discrepancy_pct",
        "total_dollar_impact",
        "low_confidence",
    }
)

# ``fetch_timeseries`` uses ``data.get("data", [])``; each point feeds ``go.Scatter``.
_DASHBOARD_TIMESERIES_POINT_KEYS: frozenset[str] = frozenset(
    {
        "date",
        "call_count",
        "reported_reasoning_tokens",
        "estimated_reasoning_tokens",
        "discrepancy_pct",
        "dollar_impact",
    }
)


def _assert_kpi_contract(data: dict[str, Any]) -> None:
    missing = _DASHBOARD_KPI_KEYS - data.keys()
    assert not missing, f"summary KPI missing keys for dashboard: {sorted(missing)}"


@pytest.mark.phase4_regression
class TestPhase4DashboardApiContract:
    """Contract tests between proxy JSON and dashboard consumers."""

    @pytest.mark.asyncio
    async def test_flat_summary_matches_dashboard_kpis(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        sample_call_log: Any,
        sample_estimation: Any,
        db_session: Any,
    ) -> None:
        """Ungrouped ``GET /v1/summary`` exposes all KPI fields the dashboard reads."""
        await db_session.commit()

        response = await client.get("/v1/summary", headers={"X-API-Key": test_api_key})
        assert response.status_code == 200
        data = response.json()
        assert "overall" not in data
        _assert_kpi_contract(data)

    @pytest.mark.asyncio
    async def test_grouped_summary_matches_dashboard_chart_contract(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        sample_call_log: Any,
        sample_estimation: Any,
        db_session: Any,
    ) -> None:
        """``group_by`` response supplies ``overall`` + ``groups`` rows for Plotly."""
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
        _assert_kpi_contract(data["overall"])
        assert len(data["groups"]) >= 1
        row = data["groups"][0]
        missing = _DASHBOARD_GROUP_KEYS - row.keys()
        assert not missing, f"group row missing keys for dashboard: {sorted(missing)}"

    @pytest.mark.asyncio
    async def test_timeseries_payload_matches_dashboard_chart_contract(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        sample_call_log: Any,
        sample_estimation: Any,
        db_session: Any,
    ) -> None:
        """``GET /v1/summary/timeseries`` returns ``data`` list items the charts need."""
        await db_session.commit()

        response = await client.get(
            "/v1/summary/timeseries",
            headers={"X-API-Key": test_api_key},
        )
        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        series = body["data"]
        assert isinstance(series, list)
        assert len(series) >= 1
        point = series[0]
        missing = _DASHBOARD_TIMESERIES_POINT_KEYS - point.keys()
        assert not missing, f"timeseries point missing keys for dashboard: {sorted(missing)}"

    @pytest.mark.asyncio
    async def test_alerts_list_matches_dashboard_banner_contract(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """``GET /v1/alerts`` returns ``alerts`` + ``total`` for the Streamlit banner."""
        response = await client.get(
            "/v1/alerts",
            headers={"X-API-Key": test_api_key},
            params={"status": "active"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert "alerts" in payload
        assert "total" in payload
        assert isinstance(payload["alerts"], list)
        assert isinstance(payload["total"], int)
