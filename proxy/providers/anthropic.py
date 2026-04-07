"""Anthropic provider adapter for the Messages API.

Handles both streaming and non-streaming requests.
Extracts thinking tokens from usage.thinking_tokens when extended thinking is enabled.
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

_DEFAULT_TIMEOUT = 300.0
_ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    """Adapter for the Anthropic Messages API.

    Extracts thinking token counts from extended-thinking-enabled responses.
    Handles Anthropic-specific auth headers (x-api-key, anthropic-version).
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        settings = get_settings()
        self._base_url = settings.anthropic_base_url
        self._default_api_key = settings.anthropic_api_key
        self._client = http_client

    def get_provider_name(self) -> str:
        """Return 'anthropic'."""
        return "anthropic"

    def _get_client(self) -> httpx.AsyncClient:
        """Return the HTTP client, creating one if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        return self._client

    def _build_headers(self, api_key: str) -> dict[str, str]:
        """Build Anthropic-specific request headers.

        Anthropic uses 'x-api-key' (not 'Authorization: Bearer')
        and requires an 'anthropic-version' header.

        Args:
            api_key: The Anthropic API key.

        Returns:
            Headers dict.
        """
        key = api_key or self._default_api_key
        return {
            "x-api-key": key,
            "anthropic-version": _ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    # ------------------------------------------------------------------
    # Non-streaming
    # ------------------------------------------------------------------

    async def forward_request(
        self,
        request: ProviderRequest,
    ) -> ProviderResponse:
        """Forward a non-streaming request to Anthropic.

        Args:
            request: The normalized provider request.

        Returns:
            ProviderResponse with timing and usage data.

        Raises:
            ProviderTimeoutError: Request exceeded timeout.
            ProviderAPIError: Anthropic returned an error.
            ProviderError: Connection or network error.
        """
        url = f"{self._base_url}/messages"
        client = self._get_client()
        headers = self._build_headers(request.provider_api_key)
        log = logger.bind(provider="anthropic", model=request.model)

        body = {**request.raw_body, "stream": False}

        t0 = time.perf_counter()
        try:
            response = await client.post(url, json=body, headers=headers)
            total_ms = (time.perf_counter() - t0) * 1000.0
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            log.error("anthropic_timeout")
            raise ProviderTimeoutError(
                provider="anthropic", timeout_seconds=_DEFAULT_TIMEOUT
            ) from exc
        except httpx.HTTPStatusError as exc:
            log.error("anthropic_api_error", status_code=exc.response.status_code)
            raise ProviderAPIError(
                provider="anthropic",
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc
        except httpx.RequestError as exc:
            log.error("anthropic_connection_error", error=str(exc))
            raise ProviderError(
                message=f"Connection error: {exc}",
                provider="anthropic",
            ) from exc

        data: dict[str, Any] = response.json()
        raw_usage = data.get("usage", {})

        log.info(
            "anthropic_request_complete",
            model=data.get("model"),
            total_ms=round(total_ms, 2),
            thinking_tokens=self.extract_reasoning_tokens(raw_usage),
        )

        return ProviderResponse(
            provider="anthropic",
            model=data.get("model", request.model),
            raw_response=data,
            raw_usage=raw_usage,
            input_tokens=raw_usage.get("input_tokens", 0),
            output_tokens=raw_usage.get("output_tokens", 0),
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

        Anthropic's streaming format uses event types:
        - message_start: contains model info
        - content_block_delta: incremental text
        - message_delta: final usage stats
        - message_stop: end of stream

        Args:
            request: The normalized provider request.

        Returns:
            Tuple of (ProviderResponse, list of raw SSE bytes).
        """
        url = f"{self._base_url}/messages"
        client = self._get_client()
        headers = self._build_headers(request.provider_api_key)
        log = logger.bind(provider="anthropic", model=request.model)

        body = {**request.raw_body, "stream": True}

        chunks: list[bytes] = []
        ttft_ms: float | None = None
        raw_usage: dict[str, Any] = {}
        model_name = request.model

        t0 = time.perf_counter()

        try:
            async with client.stream(
                "POST", url, json=body, headers=headers, timeout=_DEFAULT_TIMEOUT
            ) as stream_response:
                stream_response.raise_for_status()

                async for raw_line in stream_response.aiter_lines():
                    line_bytes = (raw_line + "\n").encode()
                    chunks.append(line_bytes)

                    if not raw_line.startswith("data: "):
                        continue

                    payload = raw_line[6:]

                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - t0) * 1000.0

                    try:
                        event_data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    event_type = event_data.get("type", "")

                    # Extract model from message_start
                    if event_type == "message_start":
                        message = event_data.get("message", {})
                        model_name = message.get("model", model_name)
                        # message_start also has initial usage
                        if "usage" in message:
                            raw_usage.update(message["usage"])

                    # message_delta has final output token counts
                    if event_type == "message_delta":
                        delta_usage = event_data.get("usage", {})
                        raw_usage.update(delta_usage)

        except httpx.TimeoutException as exc:
            log.error("anthropic_stream_timeout")
            raise ProviderTimeoutError(
                provider="anthropic", timeout_seconds=_DEFAULT_TIMEOUT
            ) from exc
        except httpx.HTTPStatusError as exc:
            log.error("anthropic_stream_api_error", status_code=exc.response.status_code)
            raise ProviderAPIError(
                provider="anthropic",
                status_code=exc.response.status_code,
                detail=exc.response.text,
            ) from exc
        except httpx.RequestError as exc:
            log.error("anthropic_stream_connection_error", error=str(exc))
            raise ProviderError(
                message=f"Stream connection error: {exc}",
                provider="anthropic",
            ) from exc

        total_ms = (time.perf_counter() - t0) * 1000.0

        log.info(
            "anthropic_stream_complete",
            model=model_name,
            total_ms=round(total_ms, 2),
            thinking_tokens=self.extract_reasoning_tokens(raw_usage),
        )

        provider_response = ProviderResponse(
            provider="anthropic",
            model=model_name,
            raw_response={},
            raw_usage=raw_usage,
            input_tokens=raw_usage.get("input_tokens", 0),
            output_tokens=raw_usage.get("output_tokens", 0),
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
        """Extract thinking tokens from Anthropic usage data.

        When extended thinking is enabled, Anthropic reports thinking tokens at:
            usage.thinking_tokens

        Args:
            raw_usage: The raw usage dict from the Anthropic response.

        Returns:
            Thinking token count, or 0 if extended thinking was not enabled.
        """
        if not raw_usage:
            return 0
        return int(raw_usage.get("thinking_tokens", 0) or 0)
