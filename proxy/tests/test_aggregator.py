"""Unit tests for the discrepancy aggregation engine.

Tests signal combination, dollar impact calculation, and honoring checks.
Reference: INSTRUCTIONS.md Section 8 (Testing Standards).
"""

from __future__ import annotations

import pytest

from proxy.estimation.aggregator import DiscrepancyAggregator
from proxy.estimation.palace import PalacePrediction
from proxy.estimation.timing import TimingEstimate


@pytest.fixture
def aggregator() -> DiscrepancyAggregator:
    """Create a fresh DiscrepancyAggregator."""
    return DiscrepancyAggregator(window_size=100)


class TestAggregateSingleCall:
    """Tests for DiscrepancyAggregator.aggregate_single_call()."""

    def test_both_signals_produces_weighted_estimate(
        self, aggregator: DiscrepancyAggregator
    ) -> None:
        """Combined estimate is a weighted average when both signals are present."""
        palace = PalacePrediction(
            estimated_tokens=8000,
            confidence_low=7000,
            confidence_high=9000,
            domain="math_reasoning",
            inference_time_ms=100.0,
            model_version="v0.1.0",
        )
        timing = TimingEstimate(
            estimated_tokens=8500,
            confidence=0.95,
            tps_used=55.0,
            r_squared=0.99,
            data_points=50,
        )

        result = aggregator.aggregate_single_call(
            reported_reasoning_tokens=10000,
            provider="openai",
            model="o3",
            palace_prediction=palace,
            timing_estimate=timing,
        )

        # Weighted: 0.7*8000 + 0.3*8500 = 8150
        assert result.combined_estimated_tokens == 8150
        assert result.palace_estimated_tokens == 8000
        assert result.timing_estimated_tokens == 8500
        assert result.discrepancy_pct > 0  # reported > estimated → positive
        assert result.dollar_impact > 0
        assert result.signals_agree is True  # 8000 vs 8500 = 6.25% diff (< 20%)

    def test_palace_only_uses_palace_estimate(self, aggregator: DiscrepancyAggregator) -> None:
        """Use PALACE estimate directly when timing is unavailable."""
        palace = PalacePrediction(
            estimated_tokens=8000,
            confidence_low=7000,
            confidence_high=9000,
            domain="code_generation",
            inference_time_ms=150.0,
            model_version="v0.1.0",
        )

        result = aggregator.aggregate_single_call(
            reported_reasoning_tokens=10000,
            provider="openai",
            model="o3",
            palace_prediction=palace,
            timing_estimate=None,
        )

        assert result.combined_estimated_tokens == 8000
        assert result.timing_estimated_tokens == 0

    def test_timing_only_uses_timing_estimate(self, aggregator: DiscrepancyAggregator) -> None:
        """Use timing estimate directly when PALACE is unavailable."""
        timing = TimingEstimate(
            estimated_tokens=8500,
            confidence=0.9,
            tps_used=55.0,
            r_squared=0.98,
            data_points=30,
        )

        result = aggregator.aggregate_single_call(
            reported_reasoning_tokens=10000,
            provider="openai",
            model="o3",
            palace_prediction=None,
            timing_estimate=timing,
        )

        assert result.combined_estimated_tokens == 8500

    def test_no_signals_uses_reported_tokens(self, aggregator: DiscrepancyAggregator) -> None:
        """Fall back to reported tokens when no estimation is available."""
        result = aggregator.aggregate_single_call(
            reported_reasoning_tokens=10000,
            provider="openai",
            model="o3",
            palace_prediction=None,
            timing_estimate=None,
        )

        assert result.combined_estimated_tokens == 10000
        assert result.discrepancy_pct == 0.0

    def test_signals_disagree_when_difference_exceeds_threshold(
        self, aggregator: DiscrepancyAggregator
    ) -> None:
        """Flag signals_agree=False when PALACE and timing differ by >20%."""
        palace = PalacePrediction(
            estimated_tokens=5000,
            confidence_low=4000,
            confidence_high=6000,
            domain="general_qa",
            inference_time_ms=100.0,
            model_version="v0.1.0",
        )
        timing = TimingEstimate(
            estimated_tokens=8000,
            confidence=0.8,
            tps_used=55.0,
            r_squared=0.85,
            data_points=25,
        )

        result = aggregator.aggregate_single_call(
            reported_reasoning_tokens=7000,
            provider="openai",
            model="o3",
            palace_prediction=palace,
            timing_estimate=timing,
        )

        # 5000 vs 8000 = 37.5% difference → signals disagree
        assert result.signals_agree is False


class TestDollarImpact:
    """Tests for dollar impact calculation."""

    def test_openai_o3_dollar_impact_calculation(self, aggregator: DiscrepancyAggregator) -> None:
        """Dollar impact for o3 uses $60/1M token rate."""
        # 2000 token overcount at $60/1M = $0.12
        impact = aggregator._compute_dollar_impact("openai", "o3", 2000)
        assert impact == pytest.approx(0.12, rel=0.01)

    def test_anthropic_dollar_impact_calculation(self, aggregator: DiscrepancyAggregator) -> None:
        """Dollar impact for Claude uses $15/1M token rate."""
        # 2000 token overcount at $15/1M = $0.03
        impact = aggregator._compute_dollar_impact("anthropic", "claude-sonnet-4-20250514", 2000)
        assert impact == pytest.approx(0.03, rel=0.01)

    def test_negative_difference_means_undercharge(self, aggregator: DiscrepancyAggregator) -> None:
        """Negative token difference = customer was undercharged."""
        impact = aggregator._compute_dollar_impact("openai", "o3", -1000)
        assert impact < 0


class TestCheckHonoring:
    """Tests for the honoring rate check."""

    def test_within_interval_is_honoring(self) -> None:
        """Reported tokens within confidence interval → honoring."""
        assert DiscrepancyAggregator.check_honoring(8500, 8000, 9000) is True

    def test_above_interval_is_not_honoring(self) -> None:
        """Reported tokens above confidence interval → not honoring."""
        assert DiscrepancyAggregator.check_honoring(10000, 8000, 9000) is False

    def test_below_interval_is_not_honoring(self) -> None:
        """Reported tokens below confidence interval → not honoring."""
        assert DiscrepancyAggregator.check_honoring(5000, 8000, 9000) is False

    def test_zero_interval_is_honoring(self) -> None:
        """When no estimation is available (0,0 interval), assume honoring."""
        assert DiscrepancyAggregator.check_honoring(10000, 0, 0) is True

    def test_at_boundary_is_honoring(self) -> None:
        """Reported tokens exactly at boundary → honoring (inclusive)."""
        assert DiscrepancyAggregator.check_honoring(8000, 8000, 9000) is True
        assert DiscrepancyAggregator.check_honoring(9000, 8000, 9000) is True


class TestSlidingWindow:
    """Tests for the aggregate sliding window."""

    @pytest.mark.asyncio
    async def test_record_discrepancy_adds_to_window(
        self, aggregator: DiscrepancyAggregator
    ) -> None:
        """Discrepancies are recorded in the per-user window."""
        await aggregator.record_discrepancy(user_id=1, discrepancy_pct=15.0, dollar_impact=0.10)
        await aggregator.record_discrepancy(user_id=1, discrepancy_pct=20.0, dollar_impact=0.15)

        assert len(aggregator._windows[1]) == 2

    @pytest.mark.asyncio
    async def test_detect_sustained_returns_none_insufficient_data(
        self, aggregator: DiscrepancyAggregator
    ) -> None:
        """Return None when not enough data points exist."""
        await aggregator.record_discrepancy(user_id=1, discrepancy_pct=25.0, dollar_impact=0.20)
        result = await aggregator.detect_sustained_discrepancy(user_id=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_sustained_below_threshold_returns_none(
        self, aggregator: DiscrepancyAggregator
    ) -> None:
        """Return None when average discrepancy is below threshold."""
        for _ in range(60):
            await aggregator.record_discrepancy(user_id=1, discrepancy_pct=5.0, dollar_impact=0.01)
        result = await aggregator.detect_sustained_discrepancy(user_id=1, threshold_pct=15.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_sustained_above_threshold_returns_result(
        self, aggregator: DiscrepancyAggregator
    ) -> None:
        """Return DiscrepancyResult when average exceeds threshold."""
        for _ in range(60):
            await aggregator.record_discrepancy(user_id=1, discrepancy_pct=20.0, dollar_impact=0.10)
        result = await aggregator.detect_sustained_discrepancy(user_id=1, threshold_pct=15.0)

        assert result is not None
        assert result.aggregate_discrepancy_pct == pytest.approx(20.0, rel=0.01)
        assert result.calls_in_window == 60
        assert result.confidence_level == "medium"  # 60 calls = medium confidence
