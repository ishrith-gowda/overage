"""Multi-signal discrepancy aggregation engine.

Combines PALACE ML estimates and timing-based estimates to produce a
weighted combined estimate, discrepancy percentage, and dollar impact.
Reference: ARCHITECTURE.md Section 7.3 (Signal Aggregation).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from proxy.estimation.palace import PalacePrediction
    from proxy.estimation.timing import TimingEstimate

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Pricing: (provider, model) → price per 1M reasoning/output tokens (USD)
# These must be kept current when providers change pricing.
# ---------------------------------------------------------------------------
TOKEN_PRICING: dict[tuple[str, str], float] = {
    # OpenAI (reasoning tokens billed at output token rate)
    ("openai", "o3"): 60.00,
    ("openai", "o4-mini"): 12.00,
    ("openai", "o3-mini"): 4.40,
    ("openai", "o1"): 60.00,
    ("openai", "o1-mini"): 12.00,
    # Anthropic (thinking tokens billed at output rate)
    ("anthropic", "claude-sonnet-4-20250514"): 15.00,
    ("anthropic", "claude-3-5-sonnet-20241022"): 15.00,
    ("anthropic", "claude-3-opus-20240229"): 75.00,
    # Google
    ("google", "gemini-2.0-flash-thinking-exp"): 3.50,
    ("google", "gemini-2.5-pro-preview"): 10.00,
}

# Default fallback price if model not in pricing table
_DEFAULT_PRICE_PER_MILLION = 15.00

# Signal weights
_PALACE_WEIGHT = 0.7
_TIMING_WEIGHT = 0.3

# Sliding window defaults
_DEFAULT_WINDOW_SIZE = 100
_DISCREPANCY_THRESHOLD_PCT = 15.0


@dataclass(frozen=True)
class AggregatedEstimate:
    """Result of combining PALACE and timing signals for a single call.

    Attributes:
        combined_estimated_tokens: Weighted combination of both signals.
        palace_estimated_tokens: PALACE model estimate (0 if unavailable).
        palace_confidence_low: Lower bound from PALACE.
        palace_confidence_high: Upper bound from PALACE.
        timing_estimated_tokens: Timing-based estimate (0 if unavailable).
        timing_tps_used: TPS rate used for timing estimate.
        timing_r_squared: R² from timing regression.
        discrepancy_pct: (reported - combined) / combined * 100.
        dollar_impact: Estimated dollar impact of the discrepancy.
        signals_agree: True if PALACE and timing agree within 20%.
        domain_classification: Prompt domain from PALACE.
        palace_model_version: PALACE model version tag.
    """

    combined_estimated_tokens: int
    palace_estimated_tokens: int = 0
    palace_confidence_low: int = 0
    palace_confidence_high: int = 0
    timing_estimated_tokens: int = 0
    timing_tps_used: float = 0.0
    timing_r_squared: float | None = None
    discrepancy_pct: float = 0.0
    dollar_impact: float = 0.0
    signals_agree: bool = True
    domain_classification: str | None = None
    palace_model_version: str = "v0.1.0"


@dataclass
class DiscrepancyResult:
    """Aggregate discrepancy over a sliding window of calls.

    Used for alerting when sustained discrepancies are detected.
    """

    aggregate_discrepancy_pct: float
    dollar_impact: float
    confidence_level: str  # "low" | "medium" | "high"
    calls_in_window: int
    both_signals_available: int


class DiscrepancyAggregator:
    """Combines PALACE and timing signals and tracks aggregate discrepancy.

    Thread-safe via asyncio.Lock for sliding window updates.
    """

    def __init__(self, window_size: int = _DEFAULT_WINDOW_SIZE) -> None:
        self._window_size = window_size
        # Per-user sliding windows of discrepancy percentages
        self._windows: dict[int, deque[float]] = defaultdict(lambda: deque(maxlen=window_size))
        self._dollar_windows: dict[int, deque[float]] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        self._lock = asyncio.Lock()

    def aggregate_single_call(
        self,
        reported_reasoning_tokens: int,
        provider: str,
        model: str,
        palace_prediction: PalacePrediction | None = None,
        timing_estimate: TimingEstimate | None = None,
    ) -> AggregatedEstimate:
        """Combine signals for a single API call.

        Uses weighted average when both signals are available.
        Falls back to whichever signal is available.

        Args:
            reported_reasoning_tokens: Provider-reported reasoning token count.
            provider: Provider name (for pricing lookup).
            model: Model name (for pricing lookup).
            palace_prediction: PALACE model estimate (None if unavailable).
            timing_estimate: Timing-based estimate (None if unavailable).

        Returns:
            AggregatedEstimate with combined estimate and discrepancy.
        """
        palace_tokens = palace_prediction.estimated_tokens if palace_prediction else 0
        timing_tokens = timing_estimate.estimated_tokens if timing_estimate else 0

        # Compute weighted combined estimate
        if palace_prediction and timing_estimate:
            combined = int(_PALACE_WEIGHT * palace_tokens + _TIMING_WEIGHT * timing_tokens)
        elif palace_prediction:
            combined = palace_tokens
        elif timing_estimate:
            combined = timing_tokens
        else:
            # No estimation available — use reported tokens (no discrepancy)
            combined = reported_reasoning_tokens

        # Compute discrepancy
        if combined > 0:
            discrepancy_pct = (reported_reasoning_tokens - combined) / combined * 100.0
        else:
            discrepancy_pct = 0.0

        # Dollar impact
        dollar_impact = self._compute_dollar_impact(
            provider, model, reported_reasoning_tokens - combined
        )

        # Check signal agreement (within 20%)
        signals_agree = True
        if palace_prediction and timing_estimate and palace_tokens > 0 and timing_tokens > 0:
            ratio = abs(palace_tokens - timing_tokens) / max(palace_tokens, timing_tokens)
            signals_agree = ratio <= 0.20

        return AggregatedEstimate(
            combined_estimated_tokens=combined,
            palace_estimated_tokens=palace_tokens,
            palace_confidence_low=palace_prediction.confidence_low if palace_prediction else 0,
            palace_confidence_high=palace_prediction.confidence_high if palace_prediction else 0,
            timing_estimated_tokens=timing_tokens,
            timing_tps_used=timing_estimate.tps_used if timing_estimate else 0.0,
            timing_r_squared=timing_estimate.r_squared if timing_estimate else None,
            discrepancy_pct=round(discrepancy_pct, 2),
            dollar_impact=round(dollar_impact, 4),
            signals_agree=signals_agree,
            domain_classification=palace_prediction.domain if palace_prediction else None,
            palace_model_version=(
                palace_prediction.model_version if palace_prediction else "v0.1.0"
            ),
        )

    async def record_discrepancy(
        self,
        user_id: int,
        discrepancy_pct: float,
        dollar_impact: float,
    ) -> None:
        """Record a discrepancy in the user's sliding window.

        Args:
            user_id: The user who made the API call.
            discrepancy_pct: Discrepancy percentage for this call.
            dollar_impact: Dollar impact for this call.
        """
        async with self._lock:
            self._windows[user_id].append(discrepancy_pct)
            self._dollar_windows[user_id].append(dollar_impact)

    async def detect_sustained_discrepancy(
        self,
        user_id: int,
        threshold_pct: float = _DISCREPANCY_THRESHOLD_PCT,
    ) -> DiscrepancyResult | None:
        """Check if aggregate discrepancy exceeds the threshold.

        Args:
            user_id: The user to check.
            threshold_pct: The discrepancy threshold to trigger an alert.

        Returns:
            DiscrepancyResult if threshold breached, None otherwise.
        """
        async with self._lock:
            window = self._windows.get(user_id)
            dollar_window = self._dollar_windows.get(user_id)

        if not window or len(window) < _DEFAULT_WINDOW_SIZE // 2:
            return None  # Not enough data

        avg_discrepancy = sum(window) / len(window)
        total_dollars = sum(dollar_window) if dollar_window else 0.0

        if abs(avg_discrepancy) < threshold_pct:
            return None  # Below threshold

        # Determine confidence level based on sample size
        n = len(window)
        if n >= _DEFAULT_WINDOW_SIZE:
            confidence = "high"
        elif n >= _DEFAULT_WINDOW_SIZE // 2:
            confidence = "medium"
        else:
            confidence = "low"

        logger.warning(
            "sustained_discrepancy_detected",
            user_id=user_id,
            avg_discrepancy_pct=round(avg_discrepancy, 2),
            total_dollar_impact=round(total_dollars, 2),
            confidence=confidence,
            calls_in_window=n,
        )

        return DiscrepancyResult(
            aggregate_discrepancy_pct=round(avg_discrepancy, 2),
            dollar_impact=round(total_dollars, 2),
            confidence_level=confidence,
            calls_in_window=n,
            both_signals_available=0,  # Tracked separately if needed
        )

    @staticmethod
    def _compute_dollar_impact(provider: str, model: str, token_difference: int) -> float:
        """Compute the dollar impact of a token count discrepancy.

        Args:
            provider: Provider name.
            model: Model name.
            token_difference: Difference (reported - estimated). Positive = overcharge.

        Returns:
            Dollar amount (positive = customer overcharged).
        """
        # Look up pricing, with partial model matching
        price = _DEFAULT_PRICE_PER_MILLION
        for (p, m), rate in TOKEN_PRICING.items():
            if p == provider and (m == model or model.startswith(m)):
                price = rate
                break

        return token_difference * (price / 1_000_000.0)

    @staticmethod
    def check_honoring(
        reported: int,
        confidence_low: int,
        confidence_high: int,
    ) -> bool:
        """Check if reported tokens fall within the confidence interval.

        Used to compute the provider 'honoring rate' metric.

        Args:
            reported: Provider-reported reasoning tokens.
            confidence_low: Lower bound of PALACE confidence interval.
            confidence_high: Upper bound of PALACE confidence interval.

        Returns:
            True if reported tokens are within the confidence interval.
        """
        if confidence_low == 0 and confidence_high == 0:
            return True  # No estimation available, assume honoring
        return confidence_low <= reported <= confidence_high
