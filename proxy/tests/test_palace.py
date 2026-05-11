"""Tests for PALACE inference and deterministic placeholder (Phase 3.2)."""

from __future__ import annotations

import pytest

from proxy.config import get_settings
from proxy.estimation.palace import PALACEEstimator, PalacePrediction


class TestDeterministicPalacePlaceholder:
    """``PalacePrediction.deterministic_from_prompt_answer`` stability."""

    def test_same_inputs_produce_identical_prediction(self) -> None:
        """Placeholder is a pure function of (prompt, answer)."""
        a = PalacePrediction.deterministic_from_prompt_answer("hello", "world")
        b = PalacePrediction.deterministic_from_prompt_answer("hello", "world")
        assert a == b

    def test_math_prompt_domain_classification(self) -> None:
        """Domain heuristic matches keyword classifier."""
        p = PalacePrediction.deterministic_from_prompt_answer("solve for x in 2x = 4", "")
        assert p.domain == "math_reasoning"

    def test_placeholder_version_tag(self) -> None:
        """Consumers can detect ML vs placeholder via model_version."""
        p = PalacePrediction.deterministic_from_prompt_answer("x", "y")
        assert p.model_version == "placeholder-deterministic-v1"
        assert p.inference_time_ms == 0.0


class TestPALACEPredictAsync:
    """``PALACEEstimator.predict`` when weights are not loaded."""

    @pytest.mark.asyncio
    async def test_predict_returns_placeholder_when_estimation_enabled_not_loaded(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When estimation is on but the model is absent, return deterministic PALACE shape."""
        monkeypatch.setenv("ESTIMATION_ENABLED", "true")
        get_settings.cache_clear()
        est = PALACEEstimator()
        assert est.is_loaded() is False
        out = await est.predict("prompt text", "answer text")
        assert out is not None
        assert out.model_version == "placeholder-deterministic-v1"
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_predict_returns_none_when_estimation_disabled_not_loaded(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When estimation is off, do not fabricate a PALACE signal."""
        monkeypatch.setenv("ESTIMATION_ENABLED", "false")
        get_settings.cache_clear()
        est = PALACEEstimator()
        assert est.is_loaded() is False
        out = await est.predict("prompt text", "answer text")
        assert out is None
        get_settings.cache_clear()
