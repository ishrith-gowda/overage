"""Timing-based reasoning token estimation.

Uses the strong correlation (Pearson >= 0.987) between output token count
and generation time to independently estimate reasoning tokens.
Reference: ARCHITECTURE.md Section 7.2 (Timing Estimation).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Default TPS (tokens-per-second) rates per model — profiled empirically.
# These are starting estimates; the sliding window refines them over time.
# ---------------------------------------------------------------------------
DEFAULT_TPS_RATES: dict[str, float] = {
    # OpenAI
    "o3": 55.0,
    "o4-mini": 80.0,
    "o3-mini": 90.0,
    "o1": 50.0,
    "o1-mini": 75.0,
    # Anthropic
    "claude-sonnet-4-20250514": 65.0,
    "claude-3-5-sonnet-20241022": 65.0,
    "claude-3-opus-20240229": 40.0,
    # Google
    "gemini-2.0-flash-thinking-exp": 70.0,
    "gemini-2.5-pro-preview": 60.0,
}

# Maximum number of data points per model in the sliding window
_MAX_WINDOW_SIZE = 1000
# Minimum data points before we use the learned regression
_MIN_DATA_POINTS = 20


@dataclass(frozen=True)
class TimingEstimate:
    """Result of a timing-based token estimation.

    Attributes:
        estimated_tokens: Estimated reasoning token count.
        confidence: Confidence score (0-1) based on R² of the regression.
        tps_used: The tokens-per-second rate used for the estimate.
        r_squared: R² correlation coefficient from the sliding window.
        data_points: Number of data points in the sliding window.
    """

    estimated_tokens: int
    confidence: float
    tps_used: float
    r_squared: float | None
    data_points: int


class TimingEstimator:
    """Estimate reasoning tokens from response latency.

    Maintains a per-model sliding window of (reported_tokens, latency_ms)
    pairs and fits a linear regression to refine TPS estimates over time.
    Thread-safe via asyncio.Lock.
    """

    def __init__(self) -> None:
        # Per-model sliding windows: model → list of (tokens, latency_ms)
        self._windows: dict[str, list[tuple[int, float]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def profile_update(
        self,
        model: str,
        reported_tokens: int,
        latency_ms: float,
    ) -> None:
        """Add a data point to the model's sliding window.

        Called after every API call to refine timing estimates.

        Args:
            model: The model identifier.
            reported_tokens: Provider-reported total output tokens.
            latency_ms: Total response latency in milliseconds.
        """
        if reported_tokens <= 0 or latency_ms <= 0:
            return

        async with self._lock:
            window = self._windows[model]
            window.append((reported_tokens, latency_ms))
            # Evict oldest entries if window exceeds max size
            if len(window) > _MAX_WINDOW_SIZE:
                self._windows[model] = window[-_MAX_WINDOW_SIZE:]

    async def estimate(
        self,
        model: str,
        latency_ms: float,
        output_tokens_non_reasoning: int = 0,
    ) -> TimingEstimate | None:
        """Estimate reasoning tokens from response latency.

        Uses either the learned regression (if enough data points exist)
        or the default TPS rate for the model.

        Args:
            model: The model identifier.
            latency_ms: Total response latency in milliseconds.
            output_tokens_non_reasoning: Non-reasoning output tokens
                (subtracted from the total estimate to isolate reasoning).

        Returns:
            TimingEstimate, or None if estimation is not possible.
        """
        if latency_ms <= 0:
            return None

        latency_s = latency_ms / 1000.0

        # Try learned regression first
        async with self._lock:
            window = self._windows.get(model, [])
            n_points = len(window)

        if n_points >= _MIN_DATA_POINTS:
            return await self._estimate_from_regression(
                model, latency_s, output_tokens_non_reasoning, window, n_points
            )

        # Fall back to default TPS rate
        tps = self._get_default_tps(model)
        if tps is None:
            logger.debug(
                "timing_no_tps_for_model",
                model=model,
                detail="No default TPS rate and insufficient data for regression",
            )
            return None

        estimated_total = int(latency_s * tps)
        estimated_reasoning = max(0, estimated_total - output_tokens_non_reasoning)

        return TimingEstimate(
            estimated_tokens=estimated_reasoning,
            confidence=0.5,  # Lower confidence without regression
            tps_used=tps,
            r_squared=None,
            data_points=n_points,
        )

    async def _estimate_from_regression(
        self,
        model: str,
        latency_s: float,
        output_tokens_non_reasoning: int,
        window: list[tuple[int, float]],
        n_points: int,
    ) -> TimingEstimate:
        """Estimate using scipy linear regression on the sliding window.

        Args:
            model: Model identifier.
            latency_s: Latency in seconds.
            output_tokens_non_reasoning: Non-reasoning output tokens.
            window: The sliding window of (tokens, latency_ms) pairs.
            n_points: Number of data points.

        Returns:
            TimingEstimate with regression-based confidence.
        """
        from scipy import stats  # type: ignore[import-untyped]

        # Linear regression: tokens = slope * latency_ms + intercept
        latencies = [lat for _, lat in window]
        tokens = [tok for tok, _ in window]

        result = stats.linregress(latencies, tokens)
        slope = result.slope
        r_squared = result.rvalue**2

        # Estimate total output tokens from latency
        estimated_total = max(0, int(slope * (latency_s * 1000.0) + result.intercept))
        estimated_reasoning = max(0, estimated_total - output_tokens_non_reasoning)

        # TPS derived from slope (tokens/ms → tokens/s)
        tps_used = slope * 1000.0

        # Confidence based on R² — higher R² = more confident
        confidence = min(1.0, max(0.0, r_squared))

        logger.debug(
            "timing_regression_estimate",
            model=model,
            estimated_reasoning=estimated_reasoning,
            r_squared=round(r_squared, 4),
            tps=round(tps_used, 2),
            data_points=n_points,
        )

        return TimingEstimate(
            estimated_tokens=estimated_reasoning,
            confidence=round(confidence, 4),
            tps_used=round(tps_used, 2),
            r_squared=round(r_squared, 4),
            data_points=n_points,
        )

    @staticmethod
    def _get_default_tps(model: str) -> float | None:
        """Look up the default TPS rate for a model.

        Tries an exact match first, then partial match on known prefixes.

        Args:
            model: The model identifier.

        Returns:
            TPS rate, or None if not found.
        """
        if model in DEFAULT_TPS_RATES:
            return DEFAULT_TPS_RATES[model]

        # Partial match: "o3-2025-04-16" should match "o3"
        for known_model, tps in DEFAULT_TPS_RATES.items():
            if model.startswith(known_model):
                return tps

        return None
