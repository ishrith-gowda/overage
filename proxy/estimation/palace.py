"""PALACE estimation engine using a LoRA-fine-tuned Qwen2.5-1.5B model.

Predicts reasoning token counts from (prompt, answer) pairs.
Runs asynchronously in a thread pool to avoid blocking the event loop.
Reference: ARCHITECTURE.md Section 7.1 (PALACE Inference).
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from proxy.config import get_settings

logger = structlog.get_logger(__name__)

# Returned when the LoRA stack is not loaded but estimation is enabled (no torch/[ml] required).
_PLACEHOLDER_MODEL_VERSION = "placeholder-deterministic-v1"
_MAX_PLACEHOLDER_TOKENS = 500_000


def classify_prompt_domain(prompt: str) -> str:
    """Keyword-based domain label shared by PALACE and deterministic fallback.

    Args:
        prompt: The user's input prompt (may be truncated JSON for proxy logs).

    Returns:
        Domain string: math_reasoning, code_generation, logical_reasoning,
        creative_writing, or general_qa.
    """
    lower = prompt.lower()

    math_keywords = {
        "solve",
        "calculate",
        "equation",
        "integral",
        "derivative",
        "proof",
        "theorem",
    }
    code_keywords = {
        "code",
        "function",
        "program",
        "debug",
        "implement",
        "class",
        "def ",
        "import ",
    }
    logic_keywords = {"logic", "reasoning", "deduce", "infer", "puzzle", "if and only if"}

    if any(kw in lower for kw in math_keywords):
        return "math_reasoning"
    if any(kw in lower for kw in code_keywords):
        return "code_generation"
    if any(kw in lower for kw in logic_keywords):
        return "logical_reasoning"
    if any(kw in lower for kw in ("story", "write", "creative", "poem", "essay")):
        return "creative_writing"
    return "general_qa"


@dataclass(frozen=True)
class PalacePrediction:
    """Result of a PALACE model prediction.

    Attributes:
        estimated_tokens: Point estimate of reasoning tokens.
        confidence_low: Lower bound of the confidence interval.
        confidence_high: Upper bound of the confidence interval.
        domain: Classified prompt domain (math, code, reasoning, etc.).
        inference_time_ms: Wall-clock inference time in milliseconds.
        model_version: Version tag of the model that produced this estimate.
    """

    estimated_tokens: int
    confidence_low: int
    confidence_high: int
    domain: str
    inference_time_ms: float
    model_version: str

    @staticmethod
    def deterministic_from_prompt_answer(prompt: str, answer: str) -> PalacePrediction:
        """Deterministic PALACE-shaped estimate when the ML stack is unavailable.

        Same ``(prompt, answer)`` always yields the same numbers so tests and
        dashboards are stable without ``[ml]`` installed or weights on disk.

        Args:
            prompt: Prompt text (or truncated JSON for logged requests).
            answer: Assistant output text (often empty in the background path).

        Returns:
            A ``PalacePrediction`` tagged with ``placeholder-deterministic-v1``.
        """
        p_len = len(prompt)
        a_len = len(answer)
        h1 = int.from_bytes(hashlib.sha256(prompt.encode()).digest()[:4], "big")
        h2 = int.from_bytes(hashlib.sha256(answer.encode()).digest()[:4], "big")
        base = max(1, p_len // 40 + a_len // 20)
        jitter = (h1 ^ h2) % 500
        estimated = min(_MAX_PLACEHOLDER_TOKENS, max(1, base + jitter))
        confidence_low = max(0, int(estimated * 0.85))
        confidence_high = int(estimated * 1.15)
        return PalacePrediction(
            estimated_tokens=estimated,
            confidence_low=confidence_low,
            confidence_high=confidence_high,
            domain=classify_prompt_domain(prompt),
            inference_time_ms=0.0,
            model_version=_PLACEHOLDER_MODEL_VERSION,
        )


class PALACEEstimator:
    """PALACE reasoning token estimator.

    Loads a LoRA-fine-tuned Qwen2.5-1.5B model and runs inference
    to predict the number of reasoning tokens from a (prompt, answer) pair.

    The model is loaded once at startup and kept in memory.
    Inference runs in a thread pool executor to avoid blocking async code.
    """

    def __init__(self) -> None:
        self._model: Any | None = None
        self._tokenizer: Any | None = None
        self._device: str = "cpu"
        self._model_version: str = get_settings().palace_model_version
        self._model_path: str = get_settings().palace_model_path
        self._loaded: bool = False

    def is_loaded(self) -> bool:
        """Check if the model is loaded and ready for inference."""
        return self._loaded

    async def load_model(self) -> bool:
        """Load the PALACE model with LoRA adapters.

        Runs the blocking model load in a thread pool.

        Returns:
            True if the model loaded successfully, False otherwise.
        """
        settings = get_settings()
        if not settings.estimation_enabled:
            logger.info("palace_model_disabled", reason="estimation_enabled=false")
            return False

        model_path = Path(self._model_path)
        if not model_path.exists():
            logger.warning(
                "palace_model_not_found",
                path=str(model_path),
                detail="Estimation will be unavailable. Proxy continues without it.",
            )
            return False

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._load_model_sync)
            self._loaded = True
            logger.info(
                "palace_model_loaded",
                path=str(model_path),
                device=self._device,
                version=self._model_version,
            )
            return True
        except Exception as exc:
            logger.error("palace_model_load_failed", error=str(exc))
            self._loaded = False
            return False

    def _load_model_sync(self) -> None:
        """Synchronous model loading (runs in thread pool).

        Imports torch/transformers here to avoid import overhead if
        the model is disabled.
        """
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._device = "cuda" if torch.cuda.is_available() else "cpu"

        self._tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]  # nosec B615
            self._model_path,
            trust_remote_code=True,
        )
        base_model = AutoModelForCausalLM.from_pretrained(  # nosec B615
            self._model_path,
            torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
            device_map=self._device,
            trust_remote_code=True,
        )
        # Load LoRA adapter on top of the base model
        self._model = PeftModel.from_pretrained(base_model, self._model_path)
        self._model.eval()

    async def predict(self, prompt: str, answer: str) -> PalacePrediction | None:
        """Predict reasoning tokens for a single (prompt, answer) pair.

        Args:
            prompt: The input prompt sent to the LLM.
            answer: The response text from the LLM.

        Returns:
            ``PalacePrediction`` from the loaded model, a **deterministic placeholder**
            when estimation is enabled but weights are not loaded, or ``None`` when
            estimation is disabled (callers should skip the PALACE signal).
        """
        if not self._loaded:
            settings = get_settings()
            if settings.estimation_enabled:
                logger.debug("palace_placeholder_used", reason="model_not_loaded")
                return PalacePrediction.deterministic_from_prompt_answer(prompt, answer)
            logger.debug("palace_predict_skipped", reason="model_not_loaded_estimation_disabled")
            return None

        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                self._predict_sync,
                prompt,
                answer,
            )
        except Exception as exc:
            logger.error("palace_predict_failed", error=str(exc))
            return None

    def _predict_sync(self, prompt: str, answer: str) -> PalacePrediction:
        """Synchronous prediction (runs in thread pool).

        Constructs the estimation prompt, tokenizes, runs inference,
        and parses the output to extract a token count estimate.
        """
        import torch

        t0 = time.perf_counter()

        # Construct the PALACE estimation prompt
        estimation_prompt = (
            "Estimate the number of reasoning tokens the language model used "
            "to generate the following answer to the given prompt.\n\n"
            f"Prompt: {prompt[:2000]}\n\n"
            f"Answer: {answer[:2000]}\n\n"
            "Estimated reasoning tokens:"
        )

        inputs = self._tokenizer(  # type: ignore[misc]
            estimation_prompt,
            return_tensors="pt",
            truncation=True,
            max_length=4096,
        ).to(self._device)

        with torch.no_grad():
            outputs = self._model.generate(  # type: ignore[union-attr]
                **inputs,
                max_new_tokens=32,
                temperature=0.1,
                do_sample=False,
            )

        # Decode only the newly generated tokens
        generated = outputs[0][inputs["input_ids"].shape[1] :]
        output_text: str = self._tokenizer.decode(generated, skip_special_tokens=True).strip()  # type: ignore[union-attr]

        # Parse the number from the output
        estimated = self._parse_token_count(output_text)
        inference_ms = (time.perf_counter() - t0) * 1000.0

        domain = classify_prompt_domain(prompt)

        # Confidence interval: ±15% for initial model version
        confidence_low = max(0, int(estimated * 0.85))
        confidence_high = int(estimated * 1.15)

        return PalacePrediction(
            estimated_tokens=estimated,
            confidence_low=confidence_low,
            confidence_high=confidence_high,
            domain=domain,
            inference_time_ms=round(inference_ms, 2),
            model_version=self._model_version,
        )

    @staticmethod
    def _parse_token_count(text: str) -> int:
        """Parse an integer token count from model output text.

        Args:
            text: The raw model output string.

        Returns:
            Parsed integer, or 0 if parsing fails.
        """
        # Extract the first number from the output
        import re

        numbers = re.findall(r"\d+", text.replace(",", ""))
        if numbers:
            return int(numbers[0])
        return 0
