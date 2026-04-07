"""Unit tests for the timing-based estimation engine.

Tests TPS lookup, sliding window updates, and regression-based estimation.
Reference: INSTRUCTIONS.md Section 8 (Testing Standards).
"""

from __future__ import annotations

import pytest

from proxy.estimation.timing import DEFAULT_TPS_RATES, TimingEstimator


@pytest.fixture
def estimator() -> TimingEstimator:
    """Create a fresh TimingEstimator instance."""
    return TimingEstimator()


class TestDefaultTPSRates:
    """Tests for the default TPS rate lookup table."""

    @pytest.mark.parametrize(
        ("model", "expected_tps"),
        [
            ("o3", 55.0),
            ("o4-mini", 80.0),
            ("o3-mini", 90.0),
            ("claude-sonnet-4-20250514", 65.0),
        ],
        ids=["openai-o3", "openai-o4-mini", "openai-o3-mini", "anthropic-sonnet"],
    )
    def test_known_models_have_tps_rates(self, model: str, expected_tps: float) -> None:
        """Known models should have default TPS rates."""
        assert DEFAULT_TPS_RATES[model] == expected_tps

    def test_partial_model_match_returns_correct_tps(self, estimator: TimingEstimator) -> None:
        """Model names with date suffixes should match their base model."""
        tps = estimator._get_default_tps("o3-2025-04-16")
        assert tps == 55.0

    def test_unknown_model_returns_none(self, estimator: TimingEstimator) -> None:
        """Unknown models should return None for TPS."""
        tps = estimator._get_default_tps("totally-unknown-model-v99")
        assert tps is None


class TestEstimate:
    """Tests for TimingEstimator.estimate()."""

    @pytest.mark.asyncio
    async def test_estimate_with_default_tps_returns_result(
        self, estimator: TimingEstimator
    ) -> None:
        """Estimate using default TPS when no profiling data exists."""
        result = await estimator.estimate(model="o3", latency_ms=10000.0)

        assert result is not None
        assert result.estimated_tokens > 0
        assert result.tps_used == 55.0
        assert result.confidence == 0.5  # Low confidence without regression
        assert result.data_points == 0

    @pytest.mark.asyncio
    async def test_estimate_zero_latency_returns_none(self, estimator: TimingEstimator) -> None:
        """Return None when latency is zero or negative."""
        assert await estimator.estimate("o3", latency_ms=0) is None
        assert await estimator.estimate("o3", latency_ms=-100) is None

    @pytest.mark.asyncio
    async def test_estimate_unknown_model_no_data_returns_none(
        self, estimator: TimingEstimator
    ) -> None:
        """Return None for unknown model with no profiling data."""
        result = await estimator.estimate("unknown-model", latency_ms=5000.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_estimate_subtracts_non_reasoning_tokens(
        self, estimator: TimingEstimator
    ) -> None:
        """Non-reasoning output tokens are subtracted from the total estimate."""
        result_with = await estimator.estimate(
            "o3", latency_ms=10000.0, output_tokens_non_reasoning=200
        )
        result_without = await estimator.estimate(
            "o3", latency_ms=10000.0, output_tokens_non_reasoning=0
        )

        assert result_with is not None
        assert result_without is not None
        assert result_with.estimated_tokens < result_without.estimated_tokens

    @pytest.mark.asyncio
    async def test_estimate_with_regression_has_higher_confidence(
        self, estimator: TimingEstimator
    ) -> None:
        """With enough data points, regression should produce higher confidence."""
        # Add 25 data points with a clear linear relationship
        for i in range(25):
            tokens = 1000 + i * 200
            latency = tokens / 55.0 * 1000.0  # Perfect linear at 55 TPS
            await estimator.profile_update("o3", tokens, latency)

        result = await estimator.estimate("o3", latency_ms=10000.0)

        assert result is not None
        assert result.confidence > 0.5  # Higher confidence with regression
        assert result.data_points == 25
        assert result.r_squared is not None
        assert result.r_squared > 0.9


class TestProfileUpdate:
    """Tests for TimingEstimator.profile_update()."""

    @pytest.mark.asyncio
    async def test_profile_update_adds_data_point(self, estimator: TimingEstimator) -> None:
        """Data points are added to the sliding window."""
        await estimator.profile_update("o3", reported_tokens=5000, latency_ms=10000.0)

        assert len(estimator._windows["o3"]) == 1

    @pytest.mark.asyncio
    async def test_profile_update_ignores_zero_values(self, estimator: TimingEstimator) -> None:
        """Zero or negative values are not added to the window."""
        await estimator.profile_update("o3", reported_tokens=0, latency_ms=10000.0)
        await estimator.profile_update("o3", reported_tokens=5000, latency_ms=0)
        await estimator.profile_update("o3", reported_tokens=-1, latency_ms=-1)

        assert len(estimator._windows["o3"]) == 0

    @pytest.mark.asyncio
    async def test_profile_window_evicts_old_entries(self, estimator: TimingEstimator) -> None:
        """Window evicts oldest entries when exceeding max size."""
        # Add more than max window size
        for i in range(1100):
            await estimator.profile_update("o3", reported_tokens=1000 + i, latency_ms=5000.0 + i)

        assert len(estimator._windows["o3"]) <= 1000
