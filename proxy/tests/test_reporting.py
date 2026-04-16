"""Tests for audit report data loading and PDF rendering (PRD Story 6)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from proxy.reporting.data import _fetch_groups, load_audit_report_bundle
from proxy.reporting.types import AuditReportBundle, AuditTopCall
from proxy.storage.models import SummaryGroupRow, SummaryStats, TimeseriesPoint

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from proxy.storage.models import APICallLog, EstimationResult, User


@pytest.mark.asyncio
async def test_load_audit_report_bundle_shapes_and_totals(
    db_session: AsyncSession,
    test_user: User,
    sample_call_log: APICallLog,
    sample_estimation: EstimationResult,
) -> None:
    """Bundle aggregates match seeded call + estimation for the report window."""
    await db_session.commit()

    end_d = datetime.now(tz=UTC).date()
    start_d = end_d - timedelta(days=30)

    bundle = await load_audit_report_bundle(
        db_session,
        test_user.id,
        "test@overage.dev",
        start_d,
        end_d,
    )

    assert bundle.user_label == "test@overage.dev"
    assert bundle.period_start == start_d
    assert bundle.period_end == end_d
    assert bundle.overall.total_calls >= 1
    reported_floor = sample_call_log.reported_reasoning_tokens
    assert bundle.overall.total_reported_reasoning_tokens >= reported_floor
    assert len(bundle.by_provider) >= 1
    assert len(bundle.by_model) >= 1
    assert len(bundle.top_calls) >= 1
    top = bundle.top_calls[0]
    assert top.call_id == sample_call_log.id
    assert top.provider == "openai"


@pytest.mark.asyncio
async def test_fetch_groups_invalid_group_by_raises(
    db_session: AsyncSession,
    test_user: User,
) -> None:
    """Invalid group_by raises a clear error (internal guard)."""
    today = datetime.now(tz=UTC).date()
    with pytest.raises(ValueError, match="group_by must be"):
        await _fetch_groups(db_session, test_user.id, today, today, "not_a_dimension")


def test_render_audit_pdf_produces_valid_pdf_bytes() -> None:
    """render_audit_pdf returns PDF magic bytes (requires fpdf2)."""
    pytest.importorskip("fpdf")

    from proxy.reporting.pdf_audit import render_audit_pdf

    start = date(2026, 1, 1)
    end = date(2026, 1, 31)
    overall = SummaryStats(
        total_calls=2,
        total_reported_reasoning_tokens=1000,
        total_estimated_reasoning_tokens=900,
        aggregate_discrepancy_pct=11.11,
        total_dollar_impact=1.25,
        avg_discrepancy_pct=10.0,
        honoring_rate_pct=50.0,
    )
    row_provider = SummaryGroupRow(
        group_key="openai",
        provider="openai",
        model=None,
        call_count=2,
        total_reported_reasoning_tokens=1000,
        total_estimated_reasoning_tokens=900,
        aggregate_discrepancy_pct=11.11,
        avg_discrepancy_pct=10.0,
        total_dollar_impact=1.25,
        low_confidence=True,
    )
    row_model = SummaryGroupRow(
        group_key="o3",
        provider=None,
        model="o3",
        call_count=2,
        total_reported_reasoning_tokens=1000,
        total_estimated_reasoning_tokens=900,
        aggregate_discrepancy_pct=11.11,
        avg_discrepancy_pct=10.0,
        total_dollar_impact=1.25,
        low_confidence=True,
    )
    top = AuditTopCall(
        call_id=1,
        provider="openai",
        model="o3",
        reported_reasoning_tokens=500,
        combined_estimated_tokens=450,
        discrepancy_pct=11.0,
        dollar_impact=0.05,
    )
    ts = (
        TimeseriesPoint(
            date="2026-01-01",
            call_count=1,
            reported_reasoning_tokens=500,
            estimated_reasoning_tokens=450,
            discrepancy_pct=10.0,
            dollar_impact=0.05,
        ),
        TimeseriesPoint(
            date="2026-01-02",
            call_count=1,
            reported_reasoning_tokens=500,
            estimated_reasoning_tokens=450,
            discrepancy_pct=10.0,
            dollar_impact=0.05,
        ),
    )
    bundle = AuditReportBundle(
        user_label="test@example.com",
        period_start=start,
        period_end=end,
        overall=overall,
        by_provider=(row_provider,),
        by_model=(row_model,),
        top_calls=(top,),
        timeseries=ts,
    )

    pdf_bytes = render_audit_pdf(bundle)
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 500


def test_render_audit_pdf_single_timeseries_bucket_skips_chart() -> None:
    """One daily bucket uses the textual fallback (no chart PNG)."""
    pytest.importorskip("fpdf")

    from proxy.reporting.pdf_audit import render_audit_pdf

    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    overall = SummaryStats(
        total_calls=1,
        total_reported_reasoning_tokens=100,
        total_estimated_reasoning_tokens=90,
        aggregate_discrepancy_pct=11.11,
        total_dollar_impact=0.1,
        avg_discrepancy_pct=10.0,
        honoring_rate_pct=0.0,
    )
    ts_single = (
        TimeseriesPoint(
            date="2026-02-01",
            call_count=1,
            reported_reasoning_tokens=100,
            estimated_reasoning_tokens=90,
            discrepancy_pct=10.0,
            dollar_impact=0.1,
        ),
    )
    bundle = AuditReportBundle(
        user_label="u",
        period_start=start,
        period_end=end,
        overall=overall,
        by_provider=(),
        by_model=(),
        top_calls=(),
        timeseries=ts_single,
    )
    pdf_bytes = render_audit_pdf(bundle)
    assert pdf_bytes[:4] == b"%PDF"
