"""Load audit report aggregates from the database (user-scoped, date range)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from proxy.reporting.types import AuditReportBundle, AuditTopCall
from proxy.storage.models import (
    APICallLog,
    EstimationResult,
    SummaryGroupRow,
    SummaryStats,
    TimeseriesPoint,
)


def _range_filters(user_id: int, start: date, end: date) -> list[Any]:
    """Timestamp window ``[start 00:00 UTC, end 23:59:59 UTC]`` for one user."""
    return [
        APICallLog.user_id == user_id,
        APICallLog.timestamp >= datetime.combine(start, datetime.min.time(), tzinfo=UTC),
        APICallLog.timestamp <= datetime.combine(end, datetime.max.time(), tzinfo=UTC),
    ]


async def _fetch_overall(
    session: AsyncSession,
    user_id: int,
    start: date,
    end: date,
) -> SummaryStats:
    """Same aggregate semantics as ``GET /v1/summary`` for the date range."""
    conds = _range_filters(user_id, start, end)
    stmt = (
        select(
            func.count(APICallLog.id).label("total_calls"),
            func.sum(APICallLog.reported_reasoning_tokens).label("total_reported"),
            func.sum(EstimationResult.combined_estimated_tokens).label("total_estimated"),
            func.avg(EstimationResult.discrepancy_pct).label("avg_discrepancy"),
            func.sum(EstimationResult.dollar_impact).label("total_dollars"),
            func.sum(
                case(
                    (
                        APICallLog.reported_reasoning_tokens.between(
                            EstimationResult.palace_confidence_low,
                            EstimationResult.palace_confidence_high,
                        ),
                        1,
                    ),
                    else_=0,
                )
            ).label("honoring_count"),
        )
        .outerjoin(EstimationResult, APICallLog.id == EstimationResult.call_id)
        .where(and_(*conds))
    )
    result = await session.execute(stmt)
    row = result.one()

    total_calls = row.total_calls or 0
    total_reported = row.total_reported or 0
    total_estimated = row.total_estimated or 0
    honoring_count = row.honoring_count or 0

    agg_pct = 0.0
    if total_estimated > 0:
        agg_pct = (total_reported - total_estimated) / total_estimated * 100.0

    honoring_rate = (honoring_count / total_calls * 100.0) if total_calls > 0 else 0.0

    return SummaryStats(
        total_calls=total_calls,
        total_reported_reasoning_tokens=total_reported,
        total_estimated_reasoning_tokens=total_estimated,
        aggregate_discrepancy_pct=round(agg_pct, 2),
        total_dollar_impact=round(float(row.total_dollars or 0), 2),
        avg_discrepancy_pct=round(float(row.avg_discrepancy or 0), 2),
        honoring_rate_pct=round(honoring_rate, 2),
    )


async def _fetch_groups(
    session: AsyncSession,
    user_id: int,
    start: date,
    end: date,
    group_by: str,
) -> list[SummaryGroupRow]:
    """Grouped aggregates for provider or model (Story 8 shape)."""
    conds = _range_filters(user_id, start, end)
    join = APICallLog.id == EstimationResult.call_id
    agg = (
        func.count(APICallLog.id).label("total_calls"),
        func.sum(APICallLog.reported_reasoning_tokens).label("total_reported"),
        func.sum(EstimationResult.combined_estimated_tokens).label("total_estimated"),
        func.avg(EstimationResult.discrepancy_pct).label("avg_discrepancy"),
        func.sum(EstimationResult.dollar_impact).label("total_dollars"),
    )

    if group_by == "provider":
        stmt = (
            select(APICallLog.provider, *agg)
            .outerjoin(EstimationResult, join)
            .where(and_(*conds))
            .group_by(APICallLog.provider)
            .order_by(APICallLog.provider)
        )
    elif group_by == "model":
        stmt = (
            select(APICallLog.model, *agg)
            .outerjoin(EstimationResult, join)
            .where(and_(*conds))
            .group_by(APICallLog.model)
            .order_by(APICallLog.model)
        )
    else:
        msg = "group_by must be provider or model"
        raise ValueError(msg)

    result = await session.execute(stmt)
    rows = result.all()
    out: list[SummaryGroupRow] = []
    for row in rows:
        if group_by == "provider":
            p, tc, trp, te, ad, td = row[0], row[1], row[2], row[3], row[4], row[5]
            gkey = str(p)
            prov: str | None = str(p)
            mdl: str | None = None
        else:
            m, tc, trp, te, ad, td = row[0], row[1], row[2], row[3], row[4], row[5]
            gkey = str(m)
            prov = None
            mdl = str(m)

        tc_i = int(tc or 0)
        trp = int(trp or 0)
        te = int(te or 0)
        agg_pct = 0.0
        if te > 0:
            agg_pct = (trp - te) / te * 100.0

        out.append(
            SummaryGroupRow(
                group_key=gkey,
                provider=prov,
                model=mdl,
                call_count=tc_i,
                total_reported_reasoning_tokens=trp,
                total_estimated_reasoning_tokens=te,
                aggregate_discrepancy_pct=round(agg_pct, 2),
                avg_discrepancy_pct=round(float(ad or 0), 2),
                total_dollar_impact=round(float(td or 0), 4),
                low_confidence=tc_i < 10,
            )
        )
    return out


async def _fetch_timeseries(
    session: AsyncSession,
    user_id: int,
    start: date,
    end: date,
) -> list[TimeseriesPoint]:
    """Daily buckets aligned with ``GET /v1/summary/timeseries``."""
    stmt = (
        select(
            func.date(APICallLog.timestamp).label("day"),
            func.count(APICallLog.id).label("call_count"),
            func.sum(APICallLog.reported_reasoning_tokens).label("reported"),
            func.sum(EstimationResult.combined_estimated_tokens).label("estimated"),
            func.avg(EstimationResult.discrepancy_pct).label("discrepancy"),
            func.sum(EstimationResult.dollar_impact).label("dollars"),
        )
        .outerjoin(EstimationResult, APICallLog.id == EstimationResult.call_id)
        .where(and_(*_range_filters(user_id, start, end)))
        .group_by(func.date(APICallLog.timestamp))
        .order_by(func.date(APICallLog.timestamp))
    )
    result = await session.execute(stmt)
    points: list[TimeseriesPoint] = []
    for row in result.all():
        points.append(
            TimeseriesPoint(
                date=str(row.day),
                call_count=row.call_count or 0,
                reported_reasoning_tokens=row.reported or 0,
                estimated_reasoning_tokens=row.estimated or 0,
                discrepancy_pct=round(float(row.discrepancy or 0), 2),
                dollar_impact=round(float(row.dollars or 0), 2),
            )
        )
    return points


async def _fetch_top_calls(
    session: AsyncSession,
    user_id: int,
    start: date,
    end: date,
    limit: int = 20,
) -> list[AuditTopCall]:
    """Highest |discrepancy_pct| calls with an estimation row."""
    stmt = (
        select(APICallLog, EstimationResult)
        .join(EstimationResult, APICallLog.id == EstimationResult.call_id)
        .where(and_(*_range_filters(user_id, start, end)))
        .order_by(func.abs(EstimationResult.discrepancy_pct).desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    out: list[AuditTopCall] = []
    for call, est in result.all():
        out.append(
            AuditTopCall(
                call_id=call.id,
                provider=call.provider,
                model=call.model,
                reported_reasoning_tokens=call.reported_reasoning_tokens,
                combined_estimated_tokens=est.combined_estimated_tokens,
                discrepancy_pct=round(est.discrepancy_pct, 2),
                dollar_impact=round(est.dollar_impact, 4),
            )
        )
    return out


async def load_audit_report_bundle(
    session: AsyncSession,
    user_id: int,
    user_label: str,
    start: date,
    end: date,
) -> AuditReportBundle:
    """Aggregate calls in ``[start, end]`` for ``user_id`` into a PDF render bundle."""
    overall = await _fetch_overall(session, user_id, start, end)
    by_provider = await _fetch_groups(session, user_id, start, end, "provider")
    by_model = await _fetch_groups(session, user_id, start, end, "model")
    ts = await _fetch_timeseries(session, user_id, start, end)
    tops = await _fetch_top_calls(session, user_id, start, end)
    return AuditReportBundle(
        user_label=user_label,
        period_start=start,
        period_end=end,
        overall=overall,
        by_provider=tuple(by_provider),
        by_model=tuple(by_model),
        top_calls=tuple(tops),
        timeseries=tuple(ts),
    )
