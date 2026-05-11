"""Persist ``DiscrepancyAlert`` rows when sustained discrepancy crosses a threshold.

The :class:`~proxy.estimation.aggregator.DiscrepancyAggregator` sliding window is
updated per call in the background estimation path; this module checks whether
the window now qualifies for an alert and inserts a row exactly once per active
alert (user must acknowledge before another ``active`` row is created).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import func, select

from proxy.storage.models import DiscrepancyAlert

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from proxy.estimation.aggregator import DiscrepancyAggregator

logger = structlog.get_logger(__name__)

# Values at or above this threshold disable automatic alert inserts (rollback / ops).
_ALERT_THRESHOLD_DISABLED = 999.0


async def maybe_persist_sustained_discrepancy_alert(
    session: AsyncSession,
    user_id: int,
    aggregator: DiscrepancyAggregator,
    *,
    threshold_pct: float,
) -> DiscrepancyAlert | None:
    """If the sliding window shows sustained drift, insert one ``active`` alert.

    Skips work when ``threshold_pct >= 999`` (disabled). Skips when the user
    already has an ``active`` alert so operators are not spammed until they ack.

    Args:
        session: Open SQLAlchemy session (caller commits).
        user_id: Tenant user id.
        aggregator: Process-wide discrepancy aggregator instance.
        threshold_pct: Absolute average discrepancy %% threshold (from settings).

    Returns:
        The new ``DiscrepancyAlert`` if one was inserted, else ``None``.
    """
    if threshold_pct >= _ALERT_THRESHOLD_DISABLED:
        return None

    sustained = await aggregator.detect_sustained_discrepancy(user_id, threshold_pct=threshold_pct)
    if sustained is None:
        return None

    existing = await session.execute(
        select(func.count(DiscrepancyAlert.id)).where(
            DiscrepancyAlert.user_id == user_id,
            DiscrepancyAlert.alert_status == "active",
        )
    )
    if (existing.scalar_one() or 0) > 0:
        return None

    window_end = datetime.now(UTC)
    window_start = window_end - timedelta(days=7)
    alert = DiscrepancyAlert(
        user_id=user_id,
        window_start=window_start,
        window_end=window_end,
        call_count=sustained.calls_in_window,
        aggregate_discrepancy_pct=sustained.aggregate_discrepancy_pct,
        dollar_impact=sustained.dollar_impact,
        confidence_level=sustained.confidence_level,
        threshold_pct=threshold_pct,
        alert_status="active",
    )
    session.add(alert)
    logger.info(
        "discrepancy_alert_inserted",
        user_id=user_id,
        aggregate_discrepancy_pct=sustained.aggregate_discrepancy_pct,
        calls_in_window=sustained.calls_in_window,
    )
    return alert
