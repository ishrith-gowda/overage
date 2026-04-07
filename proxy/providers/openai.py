"""OpenAI provider adapter with streaming SSE support.

Handles both non-streaming and streaming requests to the OpenAI Chat Completions API.
Extracts reasoning tokens from usage.completion_tokens_details.reasoning_tokens.
Reference: INSTRUCTIONS.md Section 12 (Provider Implementation Patterns).
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import structlog

from proxy.config import get_settings
from proxy.exceptions import ProviderAPIError, ProviderError, ProviderTimeoutError
from proxy.providers.base import LLMProvider, ProviderRequest, ProviderResponse

logger = structlog.get_logger(__name__)

# Timeout for reasoning models can be very long (o3 can take minutes)
_DEFAULT_TIMEOUT = 300.0


class OpenAIProvider(LLMProvider):
    """Adapter for the OpenAI Chat Completions API.

    Supports both streaming (SSE) and non-streaming modes.
    Extracts reasoning token counts from o-series models.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._base_url = settings.openai_base_url
        self._default_api_key = settings.openai_api_key
        # Allow injecting a client for testing
        self._client = http_client

    def get_provider_name(self) -> str:
        """Return 'openai'."""
        return "openai"

    def _get_client(self) -> httpx.AsyncClient:
        """Return the HTTP client, creating one if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        return self._client

    def _build_headers(self, api_key: str) -> dict[str, str]:
        """Build request headers for the OpenAI API.

        Args:
            api_key: The OpenAI API key.

        Returns:
            Headers dict with Authorization and Content-Type.
        """
        key = api_key or self._default_api_key
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------

    async def forward_request(
        self,
        request: ProviderRequest,
    ) -> ProviderResponse:
        """Forward a non-streaming request to OpenAI.

        Args:
            request: The normalized provider request.

        Returns:
            ProviderResponse with timing and usage data.

        Raises:
            ProviderTimeoutError: Request exceeded timeout.
            ProviderAPIError: OpenAI returned an error HTTP status.
            ProviderError: Connection or other network error.
        """
        url = f"{self._base_url}/chat/completions"
        client = self._get_client()
        headers = self._build_headers(request.provider_api_key)
        log = logger.bind(provider="openai", model=request.model)

        # Ensure stream=false for non-streaming path
        body = {**request.raw_body, "stream": False}

        t0 = time.perf_counter()
        try:
            response = await client.post(url, json=body, headers=headers)
            total_ms = (time.perf_counter() - t0) * 1000.0
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            elapsed = (time.perf_counter() - t0) * 1000.0
            log.error("openai_timeout", elapsed_ms=elapsed)
            raise ProviderTimeoutError(provider="openai", timeout_seconds=_DEFAULT_TIMEOUT) from exc
        except httpx.HTTPStatusError as exc:
            elapsed = (time.perf_counter() - t0) * 1000.0
            log.error(
                "openai_api_error",
                status_code=exc.response.status_code,
                elapsed_ms=elapsed,
            )
            raise ProviderAPIError(
                provider="openai",
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc
        except httpx.RequestError as exc:
            log.error("openai_connection_error", error=str(exc))
            raise ProviderError(
                message=f"Connection error: {exc}",
                provider="openai",
            ) from exc

        data: dict[str, Any] = response.json()
        raw_usage = data.get("usage", {})

        log.info(
            "openai_request_complete",
            model=data.get("model"),
            total_ms=round(total_ms, 2),
            reasoning_tokens=self.extract_reasoning_tokens(raw_usage),
        )

        return ProviderResponse(
            provider="openai",
            model=data.get("model", request.model),
            raw_response=data,
            raw_usage=raw_usage,
            input_tokens=raw_usage.get("prompt_tokens", 0),
            output_tokens=raw_usage.get("completion_tokens", 0),
            reasoning_tokens=self.extract_reasoning_tokens(raw_usage),
            total_latency_ms=total_ms,
            ttft_ms=None,
            status_code=response.status_code,
            is_streaming=False,
        )

    # ------------------------------------------------------------------
    # Streaming SSE
    # ------------------------------------------------------------------

    async def forward_streaming_request(
        self,
        request: ProviderRequest,
    ) -> tuple[ProviderResponse, list[bytes]]:
        """Forward a streaming request and collect all SSE chunks.

        Accumulates all chunks for the client to replay, while extracting
        timing and usage from the final chunk. The stream_options.include_usage
        flag is injected so the final chunk contains token usage.

        Args:
            request: The normalized provider request.

        Returns:
            Tuple of (ProviderResponse, list of raw SSE bytes).
        """
        url = f"{self._base_url}/chat/completions"
        client = self._get_client()
        headers = self._build_headers(request.provider_api_key)
        log = logger.bind(provider="openai", model=request.model)

        # Force stream=true and request usage in the final chunk
        body = {
            **request.raw_body,
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        chunks: list[bytes] = []
        ttft_ms: float | None = None
        raw_usage: dict[str, Any] = {}
        model_name = request.model

        t0 = time.perf_counter()

        try:
            async with client.stream(
                "POST",
                url,
                json=body,
                headers=headers,
                timeout=_DEFAULT_TIMEOUT,
            ) as stream_response:
                stream_response.raise_for_status()

                async for raw_line in stream_response.aiter_lines():
                    if not raw_line.startswith("data: "):
                        # SSE comment or empty line — pass through
                        line_bytes = (raw_line + "\n").encode()
                        chunks.append(line_bytes)
                        continue

                    payload = raw_line[6:]  # strip "data: " prefix

                    # Record time-to-first-token on the first data chunk
                    if ttft_ms is None and payload != "[DONE]":
                        ttft_ms = (time.perf_counter() - t0) * 1000.0

                    # Re-serialize as SSE bytes for the client
                    line_bytes = (raw_line + "\n\n").encode()
                    chunks.append(line_bytes)

                    if payload == "[DONE]":
                        continue

                    # Parse the chunk to check for usage data
                    try:
                        chunk_data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    # Extract model name from first chunk
                    if chunk_model := chunk_data.get("model"):
                        model_name = chunk_model

                    # The final chunk with stream_options.include_usage has a
                    # top-level "usage" field
                    if "usage" in chunk_data and chunk_data["usage"] is not None:
                        raw_usage = chunk_data["usage"]

        except httpx.TimeoutException as exc:
            log.error("openai_stream_timeout")
            raise ProviderTimeoutError(provider="openai", timeout_seconds=_DEFAULT_TIMEOUT) from exc
        except httpx.HTTPStatusError as exc:
            log.error("openai_stream_api_error", status_code=exc.response.status_code)
            raise ProviderAPIError(
                provider="openai",
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc
        except httpx.RequestError as exc:
            log.error("openai_stream_connection_error", error=str(exc))
            raise ProviderError(
                message=f"Stream connection error: {exc}",
                provider="openai",
            ) from exc

        total_ms = (time.perf_counter() - t0) * 1000.0

        log.info(
            "openai_stream_complete",
            model=model_name,
            total_ms=round(total_ms, 2),
            ttft_ms=round(ttft_ms, 2) if ttft_ms else None,
            chunks=len(chunks),
            reasoning_tokens=self.extract_reasoning_tokens(raw_usage),
        )

        provider_response = ProviderResponse(
            provider="openai",
            model=model_name,
            raw_response={},  # Streaming has no single response body
            raw_usage=raw_usage,
            input_tokens=raw_usage.get("prompt_tokens", 0),
            output_tokens=raw_usage.get("completion_tokens", 0),
            reasoning_tokens=self.extract_reasoning_tokens(raw_usage),
            total_latency_ms=total_ms,
            ttft_ms=ttft_ms,
            status_code=200,
            is_streaming=True,
        )
        return provider_response, chunks

    # ------------------------------------------------------------------
    # Usage extraction
    # ------------------------------------------------------------------

    def extract_reasoning_tokens(self, raw_usage: dict[str, Any]) -> int:
        """Extract reasoning tokens from OpenAI usage data.

        OpenAI reports reasoning tokens at:
            usage.completion_tokens_details.reasoning_tokens

        For non-reasoning models (gpt-4o, etc.) this field is absent or 0.

        Args:
            raw_usage: The raw usage dict from the OpenAI response.

        Returns:
            Reasoning token count, or 0 if not present.
        """
        if not raw_usage:
            return 0

        details = raw_usage.get("completion_tokens_details")
        if details is None:
            return 0

        # Handle both dict and potential nested object
        if isinstance(details, dict):
            return int(details.get("reasoning_tokens", 0) or 0)

        return 0
