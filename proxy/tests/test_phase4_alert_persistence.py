"""Phase 4.5 — sustained discrepancy alerts persisted to the database.

Covers ``maybe_persist_sustained_discrepancy_alert`` and the background
``_record_and_estimate`` path (isolated aggregator tests, patched aggregate
integration, and an optional full PALACE+timing+aggregator pipeline test).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import func, select

from proxy.api import routes as routes_module
from proxy.api.routes import _record_and_estimate
from proxy.config import get_settings
from proxy.estimation.aggregator import AggregatedEstimate, DiscrepancyAggregator
from proxy.estimation.alert_persistence import maybe_persist_sustained_discrepancy_alert
from proxy.estimation.timing import TimingEstimator
from proxy.main import create_app
from proxy.storage.models import APICallLog, DiscrepancyAlert, EstimationResult, User
from proxy.tests.conftest import async_sqlite_session_factory, install_test_database_override

if TYPE_CHECKING:
    import httpx


@pytest.fixture
def estimation_on_settings() -> MagicMock:
    """Settings fragment used where only estimation + alert knobs matter."""
    s = MagicMock()
    s.estimation_enabled = True
    s.discrepancy_alert_threshold_pct = 15.0
    return s


@pytest.mark.asyncio
async def test_maybe_persist_inserts_active_alert_after_window(
    db_session: Any,
    test_user: User,
) -> None:
    """After 50 high-drift records, one active DiscrepancyAlert row is inserted."""
    agg = DiscrepancyAggregator()
    uid = test_user.id
    for _ in range(50):
        await agg.record_discrepancy(uid, discrepancy_pct=20.0, dollar_impact=0.05)

    row = await maybe_persist_sustained_discrepancy_alert(db_session, uid, agg, threshold_pct=15.0)
    assert row is not None
    assert row.alert_status == "active"
    assert row.call_count >= 50
    assert abs(row.aggregate_discrepancy_pct - 20.0) < 0.01

    await db_session.commit()

    n = await db_session.execute(
        select(func.count(DiscrepancyAlert.id)).where(DiscrepancyAlert.user_id == uid)
    )
    assert n.scalar_one() == 1


@pytest.mark.asyncio
async def test_maybe_persist_dedupes_while_active_alert_exists(
    db_session: Any,
    test_user: User,
) -> None:
    """A second sustained detection does not insert while an active row exists."""
    agg = DiscrepancyAggregator()
    uid = test_user.id
    for _ in range(50):
        await agg.record_discrepancy(uid, discrepancy_pct=20.0, dollar_impact=0.05)

    first = await maybe_persist_sustained_discrepancy_alert(
        db_session, uid, agg, threshold_pct=15.0
    )
    assert first is not None
    await db_session.commit()

    for _ in range(10):
        await agg.record_discrepancy(uid, discrepancy_pct=20.0, dollar_impact=0.05)

    second = await maybe_persist_sustained_discrepancy_alert(
        db_session, uid, agg, threshold_pct=15.0
    )
    assert second is None
    await db_session.commit()

    n = await db_session.execute(
        select(func.count(DiscrepancyAlert.id)).where(DiscrepancyAlert.user_id == uid)
    )
    assert n.scalar_one() == 1


@pytest.mark.asyncio
async def test_maybe_persist_skips_when_threshold_disabled(
    db_session: Any,
    test_user: User,
) -> None:
    """threshold_pct >= 999 disables automatic inserts."""
    agg = DiscrepancyAggregator()
    uid = test_user.id
    for _ in range(50):
        await agg.record_discrepancy(uid, discrepancy_pct=20.0, dollar_impact=0.05)

    row = await maybe_persist_sustained_discrepancy_alert(db_session, uid, agg, threshold_pct=999.0)
    assert row is None
    await db_session.commit()

    n = await db_session.execute(
        select(func.count(DiscrepancyAlert.id)).where(DiscrepancyAlert.user_id == uid)
    )
    assert n.scalar_one() == 0


@pytest.mark.asyncio
async def test_record_and_estimate_persists_alert_when_window_sustained(
    client: httpx.AsyncClient,
    test_user: User,
    test_api_key: str,
    estimation_on_settings: MagicMock,
) -> None:
    """Background path records discrepancy and inserts one alert before commit."""
    _ = client, test_api_key
    session_factory = async_sqlite_session_factory()
    fixed = AggregatedEstimate(
        combined_estimated_tokens=8000,
        palace_estimated_tokens=8000,
        palace_confidence_low=7000,
        palace_confidence_high=9000,
        timing_estimated_tokens=8500,
        timing_tps_used=55.0,
        timing_r_squared=0.99,
        discrepancy_pct=20.0,
        dollar_impact=0.1,
        signals_agree=True,
        domain_classification="general_qa",
        palace_model_version="v-test",
    )
    fresh_agg = DiscrepancyAggregator()

    with (
        patch.object(routes_module, "aggregator", fresh_agg),
        patch.object(fresh_agg, "aggregate_single_call", return_value=fixed),
        patch("proxy.api.routes.get_session_factory", return_value=session_factory),
        patch("proxy.api.routes.get_settings", return_value=estimation_on_settings),
    ):
        for i in range(50):
            await _record_and_estimate(
                user_id=test_user.id,
                provider_name="openai",
                model="o3",
                prov_response_dict={
                    "input_tokens": 10,
                    "output_tokens": 9100 + i,
                    "reasoning_tokens": 9000,
                    "total_latency_ms": 50.0 + float(i) * 3.0,
                    "ttft_ms": None,
                    "is_streaming": False,
                    "raw_usage": {},
                },
                body={"model": "o3", "messages": [{"role": "user", "content": f"c{i}"}]},
                request_id=f"req_phase4_{i}",
            )

    async with session_factory() as session:
        cnt = await session.execute(
            select(func.count(DiscrepancyAlert.id)).where(
                DiscrepancyAlert.user_id == test_user.id,
                DiscrepancyAlert.alert_status == "active",
            )
        )
        assert cnt.scalar_one() == 1

        calls = await session.execute(
            select(func.count(APICallLog.id)).where(APICallLog.user_id == test_user.id)
        )
        assert calls.scalar_one() == 50

        est = await session.execute(select(func.count(EstimationResult.id)))
        assert est.scalar_one() == 50


@pytest.mark.phase4_regression
@pytest.mark.asyncio
async def test_record_and_estimate_full_estimation_pipeline_inserts_alert(
    monkeypatch: pytest.MonkeyPatch,
    test_user: User,
    test_api_key: str,
) -> None:
    """Background path uses real ``aggregate_single_call`` (no aggregate mock).

    Exercises placeholder PALACE, :class:`~proxy.estimation.timing.TimingEstimator`
    regression, ``DiscrepancyAggregator`` sliding window, and
    ``maybe_persist_sustained_discrepancy_alert`` end-to-end against the pytest
    SQLite database. Provider HTTP remains out of scope; token fields are
    synthetic but consistent so production-shaped code paths run.
    """
    _ = test_api_key
    try:
        monkeypatch.setenv("ESTIMATION_ENABLED", "true")
        monkeypatch.setenv("DISCREPANCY_ALERT_THRESHOLD_PCT", "15")
        get_settings.cache_clear()

        app = create_app()
        install_test_database_override(app)

        session_factory = async_sqlite_session_factory()
        body = {"model": "o3", "messages": [{"role": "user", "content": "y" * 500}]}

        fresh_agg = DiscrepancyAggregator()
        fresh_timing = TimingEstimator()

        async with LifespanManager(app):
            with (
                patch.object(routes_module, "aggregator", fresh_agg),
                patch.object(routes_module, "timing_estimator", fresh_timing),
                patch("proxy.api.routes.get_session_factory", return_value=session_factory),
            ):
                for i in range(50):
                    latency = 40000.0 + float(i) * 1200.0
                    await _record_and_estimate(
                        user_id=test_user.id,
                        provider_name="openai",
                        model="o3",
                        prov_response_dict={
                            "input_tokens": 10,
                            "output_tokens": 9100,
                            "reasoning_tokens": 9000,
                            "total_latency_ms": latency,
                            "ttft_ms": None,
                            "is_streaming": False,
                            "raw_usage": {},
                        },
                        body=body,
                        request_id=f"req_phase4_full_{i}",
                    )

        async with session_factory() as session:
            cnt = await session.execute(
                select(func.count(DiscrepancyAlert.id)).where(
                    DiscrepancyAlert.user_id == test_user.id,
                    DiscrepancyAlert.alert_status == "active",
                )
            )
            assert cnt.scalar_one() == 1

            calls = await session.execute(
                select(func.count(APICallLog.id)).where(APICallLog.user_id == test_user.id)
            )
            assert calls.scalar_one() == 50

            est = await session.execute(select(func.count(EstimationResult.id)))
            assert est.scalar_one() == 50
    finally:
        get_settings.cache_clear()
