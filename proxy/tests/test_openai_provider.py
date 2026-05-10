"""Unit tests for the OpenAI provider adapter.

Tests usage extraction, error handling, and streaming behavior.
Reference: INSTRUCTIONS.md Section 8 (Testing Standards).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from proxy.exceptions import ProviderAPIError, ProviderTimeoutError
from proxy.providers.base import ProviderRequest
from proxy.providers.openai import OpenAIProvider


@pytest.fixture
def provider() -> OpenAIProvider:
    """Create an OpenAI provider with a mock HTTP client."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    return OpenAIProvider(http_client=mock_client)


@pytest.fixture
def sample_request() -> ProviderRequest:
    """Create a sample provider request."""
    return ProviderRequest(
        provider="openai",
        model="o3",
        messages=[{"role": "user", "content": "What is 2+2?"}],
        raw_body={"model": "o3", "messages": [{"role": "user", "content": "What is 2+2?"}]},
        stream=False,
        provider_api_key="sk-test-key",
    )


class TestExtractReasoningTokens:
    """Tests for OpenAIProvider.extract_reasoning_tokens()."""

    def test_extract_valid_reasoning_tokens_returns_correct_count(
        self, provider: OpenAIProvider
    ) -> None:
        """Extract reasoning tokens from a valid usage dict."""
        usage = {
            "prompt_tokens": 50,
            "completion_tokens": 1500,
            "total_tokens": 1550,
            "completion_tokens_details": {"reasoning_tokens": 1200},
        }
        assert provider.extract_reasoning_tokens(usage) == 1200

    def test_extract_zero_reasoning_tokens_returns_zero(self, provider: OpenAIProvider) -> None:
        """Return 0 when reasoning_tokens field is explicitly 0."""
        usage = {
            "completion_tokens_details": {"reasoning_tokens": 0},
        }
        assert provider.extract_reasoning_tokens(usage) == 0

    def test_extract_missing_details_returns_zero(self, provider: OpenAIProvider) -> None:
        """Return 0 when completion_tokens_details is absent."""
        usage = {"prompt_tokens": 50, "completion_tokens": 100}
        assert provider.extract_reasoning_tokens(usage) == 0

    def test_extract_none_details_returns_zero(self, provider: OpenAIProvider) -> None:
        """Return 0 when completion_tokens_details is None."""
        usage = {"completion_tokens_details": None}
        assert provider.extract_reasoning_tokens(usage) == 0

    def test_extract_empty_usage_returns_zero(self, provider: OpenAIProvider) -> None:
        """Return 0 when usage dict is empty."""
        assert provider.extract_reasoning_tokens({}) == 0

    def test_extract_none_reasoning_value_returns_zero(self, provider: OpenAIProvider) -> None:
        """Return 0 when reasoning_tokens is None (not just missing)."""
        usage = {"completion_tokens_details": {"reasoning_tokens": None}}
        assert provider.extract_reasoning_tokens(usage) == 0

    @pytest.mark.parametrize(
        ("reasoning_tokens", "expected"),
        [
            (100, 100),
            (10000, 10000),
            (50000, 50000),
        ],
        ids=["small", "medium", "large"],
    )
    def test_extract_various_token_counts(
        self, provider: OpenAIProvider, reasoning_tokens: int, expected: int
    ) -> None:
        """Correctly extract various reasoning token counts."""
        usage = {"completion_tokens_details": {"reasoning_tokens": reasoning_tokens}}
        assert provider.extract_reasoning_tokens(usage) == expected


class TestForwardRequest:
    """Tests for OpenAIProvider.forward_request()."""

    @pytest.mark.asyncio
    async def test_forward_success_returns_provider_response(
        self,
        provider: OpenAIProvider,
        sample_request: ProviderRequest,
        mock_openai_response: Any,
    ) -> None:
        """Successfully forward a request and extract usage."""
        response_data = mock_openai_response(reasoning_tokens=5000)
        mock_http_response = MagicMock(spec=httpx.Response)
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = response_data
        mock_http_response.raise_for_status = MagicMock()

        provider._client.post = AsyncMock(return_value=mock_http_response)  # type: ignore[union-attr,method-assign]

        result = await provider.forward_request(sample_request)

        assert result.provider == "openai"
        assert result.model == "o3"
        assert result.reasoning_tokens == 5000
        assert result.input_tokens == 100
        assert result.total_latency_ms > 0
        assert result.is_streaming is False

    @pytest.mark.asyncio
    async def test_forward_timeout_raises_timeout_error(
        self,
        provider: OpenAIProvider,
        sample_request: ProviderRequest,
    ) -> None:
        """Raise ProviderTimeoutError on httpx timeout."""
        provider._client.post = AsyncMock(  # type: ignore[union-attr,method-assign]
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        with pytest.raises(ProviderTimeoutError):
            await provider.forward_request(sample_request)

    @pytest.mark.asyncio
    async def test_forward_http_error_raises_api_error(
        self,
        provider: OpenAIProvider,
        sample_request: ProviderRequest,
    ) -> None:
        """Raise ProviderAPIError on HTTP 4xx/5xx."""
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 429
        error_response.text = "Rate limit exceeded"

        provider._client.post = AsyncMock(  # type: ignore[union-attr,method-assign]
            side_effect=httpx.HTTPStatusError("429", request=MagicMock(), response=error_response)
        )

        with pytest.raises(ProviderAPIError) as exc_info:
            await provider.forward_request(sample_request)
        assert exc_info.value.upstream_status_code == 429

    @pytest.mark.asyncio
    async def test_forward_connection_error_raises_provider_error(
        self,
        provider: OpenAIProvider,
        sample_request: ProviderRequest,
    ) -> None:
        """Raise ProviderError on connection failure."""
        from proxy.exceptions import ProviderError

        provider._client.post = AsyncMock(  # type: ignore[union-attr,method-assign]
            side_effect=httpx.ConnectError("Connection refused")
        )

        with pytest.raises(ProviderError, match="Connection error"):
            await provider.forward_request(sample_request)


class TestGetProviderName:
    """Tests for OpenAIProvider.get_provider_name()."""

    def test_returns_openai(self, provider: OpenAIProvider) -> None:
        """Provider name is 'openai'."""
        assert provider.get_provider_name() == "openai"


class TestForwardStreamingRequest:
    """Tests for OpenAIProvider.forward_streaming_request() (Phase 1.6)."""

    @pytest.mark.asyncio
    async def test_streaming_collects_usage_and_sets_ttft(
        self,
        provider: OpenAIProvider,
        sample_request: ProviderRequest,
    ) -> None:
        """SSE lines with final usage chunk yield reasoning tokens and TTFT."""
        stream_request = ProviderRequest(
            provider=sample_request.provider,
            model=sample_request.model,
            messages=sample_request.messages,
            raw_body={**sample_request.raw_body, "stream": True},
            stream=True,
            provider_api_key=sample_request.provider_api_key,
        )

        usage_payload = {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
                "completion_tokens_details": {"reasoning_tokens": 777},
            }
        }
        usage_sse = f"data: {json.dumps(usage_payload)}\n"
        sse_lines = [
            'data: {"choices":[{"delta":{"content":"hello"}}]}\n',
            usage_sse,
            "data: [DONE]\n",
        ]

        class _FakeStreamBody:
            def __init__(self, lines: list[str]) -> None:
                self._lines = iter(lines)

            async def aiter_lines(self) -> Any:
                for line in self._lines:
                    yield line

            def raise_for_status(self) -> None:
                return None

        fake_stream = _FakeStreamBody(sse_lines)
        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=fake_stream)
        stream_cm.__aexit__ = AsyncMock(return_value=False)
        provider._get_client()
        assert provider._client is not None
        provider._client.stream = MagicMock(return_value=stream_cm)  # type: ignore[method-assign]

        prov_res, chunks = await provider.forward_streaming_request(stream_request)

        assert prov_res.is_streaming is True
        assert prov_res.reasoning_tokens == 777
        assert prov_res.ttft_ms is not None
        assert len(chunks) > 0
