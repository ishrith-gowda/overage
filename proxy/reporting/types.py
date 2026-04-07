"""Typed payloads assembled for PDF audit rendering (PRD Story 6)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date

    from proxy.storage.models import SummaryGroupRow, SummaryStats, TimeseriesPoint


@dataclass(frozen=True)
class AuditTopCall:
    """One row in the highest-discrepancy section of the audit PDF."""

    call_id: int
    provider: str
    model: str
    reported_reasoning_tokens: int
    combined_estimated_tokens: int
    discrepancy_pct: float
    dollar_impact: float


@dataclass(frozen=True)
class AuditReportBundle:
    """Structured inputs for :func:`proxy.reporting.pdf_audit.render_audit_pdf`."""

    user_label: str
    period_start: date
    period_end: date
    overall: SummaryStats
    by_provider: tuple[SummaryGroupRow, ...]
    by_model: tuple[SummaryGroupRow, ...]
    top_calls: tuple[AuditTopCall, ...]
    timeseries: tuple[TimeseriesPoint, ...]
