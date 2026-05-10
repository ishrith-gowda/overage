"""Unit tests for the Anthropic Messages API provider adapter.

Covers ``extract_reasoning_tokens``, non-streaming forward, errors, and streaming
SSE parsing. Reference: INSTRUCTIONS.md Section 8; ROADMAP Phase 2.3 / 2.8.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from proxy.exceptions import ProviderAPIError, ProviderError, ProviderTimeoutError
from proxy.providers.anthropic import AnthropicProvider
from proxy.providers.base import ProviderRequest


@pytest.fixture
def provider() -> AnthropicProvider:
    """Anthropic provider with a mock HTTP client."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    return AnthropicProvider(http_client=mock_client)


@pytest.fixture
def sample_request() -> ProviderRequest:
    """Sample Messages API request."""
    return ProviderRequest(
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        messages=[{"role": "user", "content": "Hello"}],
        raw_body={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 256,
            "messages": [{"role": "user", "content": "Hello"}],
        },
        stream=False,
        provider_api_key="sk-ant-test",
    )


class TestExtractReasoningTokens:
    """Tests for ``AnthropicProvider.extract_reasoning_tokens`` (extended thinking)."""

    def test_extract_present_thinking_tokens(self, provider: AnthropicProvider) -> None:
        """Return integer when ``thinking_tokens`` is present."""
        raw = {"input_tokens": 10, "output_tokens": 20, "thinking_tokens": 1200}
        assert provider.extract_reasoning_tokens(raw) == 1200

    def test_extract_zero_thinking_tokens(self, provider: AnthropicProvider) -> None:
        """Explicit zero yields 0."""
        assert provider.extract_reasoning_tokens({"thinking_tokens": 0}) == 0

    def test_extract_missing_field_returns_zero(self, provider: AnthropicProvider) -> None:
        """No extended thinking → missing key → 0."""
        assert provider.extract_reasoning_tokens({"input_tokens": 1, "output_tokens": 2}) == 0

    def test_extract_empty_usage_returns_zero(self, provider: AnthropicProvider) -> None:
        assert provider.extract_reasoning_tokens({}) == 0

    def test_extract_none_thinking_returns_zero(self, provider: AnthropicProvider) -> None:
        """``thinking_tokens: null`` should not raise and should read as 0."""
        assert provider.extract_reasoning_tokens({"thinking_tokens": None}) == 0

    @pytest.mark.parametrize(
        ("thinking_tokens", "expected"),
        [(1, 1), (10_000, 10_000), (50_000, 50_000)],
        ids=["small", "medium", "large"],
    )
    def test_extract_various_counts(
        self, provider: AnthropicProvider, thinking_tokens: int, expected: int
    ) -> None:
        assert provider.extract_reasoning_tokens({"thinking_tokens": thinking_tokens}) == expected


class TestForwardRequest:
    """Non-streaming ``forward_request`` behaviour."""

    @pytest.mark.asyncio
    async def test_forward_success_returns_provider_response(
        self,
        provider: AnthropicProvider,
        sample_request: ProviderRequest,
        mock_anthropic_response: Any,
    ) -> None:
        """POST /messages JSON is merged with ``stream: false``; usage is parsed."""
        data = mock_anthropic_response(thinking_tokens=333)
        mock_http = MagicMock(spec=httpx.Response)
        mock_http.status_code = 200
        mock_http.json.return_value = data
        mock_http.raise_for_status = MagicMock()

        provider._client.post = AsyncMock(return_value=mock_http)  # type: ignore[union-attr,method-assign]

        result = await provider.forward_request(sample_request)

        assert result.provider == "anthropic"
        assert result.model == data["model"]
        assert result.reasoning_tokens == 333
        assert result.input_tokens == data["usage"]["input_tokens"]
        assert result.output_tokens == data["usage"]["output_tokens"]
        assert result.is_streaming is False
        call_kw = provider._client.post.await_args.kwargs  # type: ignore[union-attr]
        assert call_kw["json"]["stream"] is False
        hdrs = call_kw["headers"]
        assert hdrs["x-api-key"] == "sk-ant-test"
        assert hdrs["anthropic-version"] == "2023-06-01"

    @pytest.mark.asyncio
    async def test_forward_timeout_raises(
        self, provider: AnthropicProvider, sample_request: ProviderRequest
    ) -> None:
        provider._client.post = AsyncMock(  # type: ignore[union-attr,method-assign]
            side_effect=httpx.TimeoutException("timeout")
        )
        with pytest.raises(ProviderTimeoutError):
            await provider.forward_request(sample_request)

    @pytest.mark.asyncio
    async def test_forward_http_error_raises_api_error(
        self, provider: AnthropicProvider, sample_request: ProviderRequest
    ) -> None:
        err = MagicMock(spec=httpx.Response)
        err.status_code = 529
        err.text = "overloaded"
        provider._client.post = AsyncMock(  # type: ignore[union-attr,method-assign]
            side_effect=httpx.HTTPStatusError("529", request=MagicMock(), response=err)
        )
        with pytest.raises(ProviderAPIError) as ei:
            await provider.forward_request(sample_request)
        assert ei.value.upstream_status_code == 529

    @pytest.mark.asyncio
    async def test_forward_connection_error_raises_provider_error(
        self, provider: AnthropicProvider, sample_request: ProviderRequest
    ) -> None:
        provider._client.post = AsyncMock(  # type: ignore[union-attr,method-assign]
            side_effect=httpx.ConnectError("nope")
        )
        with pytest.raises(ProviderError, match="Connection error"):
            await provider.forward_request(sample_request)


class TestGetProviderName:
    def test_returns_anthropic(self, provider: AnthropicProvider) -> None:
        assert provider.get_provider_name() == "anthropic"


class TestForwardStreamingRequest:
    """``forward_streaming_request`` parses Anthropic SSE ``data:`` JSON events."""

    @pytest.mark.asyncio
    async def test_streaming_merges_usage_and_sets_ttft(
        self, provider: AnthropicProvider, sample_request: ProviderRequest
    ) -> None:
        stream_req = ProviderRequest(
            provider=sample_request.provider,
            model=sample_request.model,
            messages=sample_request.messages,
            raw_body={**sample_request.raw_body, "stream": True},
            stream=True,
            provider_api_key=sample_request.provider_api_key,
        )
        start = {
            "type": "message_start",
            "message": {
                "model": "claude-sonnet-4-20250514",
                "usage": {"input_tokens": 3},
            },
        }
        delta = {"type": "message_delta", "usage": {"output_tokens": 7, "thinking_tokens": 888}}
        lines = [
            f"data: {json.dumps(start)}\n",
            f"data: {json.dumps(delta)}\n",
        ]

        class _FakeStream:
            def __init__(self, ls: list[str]) -> None:
                self._it = iter(ls)

            async def aiter_lines(self) -> Any:
                for ln in self._it:
                    yield ln.rstrip("\n")

            def raise_for_status(self) -> None:
                return None

        fake = _FakeStream(lines)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=fake)
        cm.__aexit__ = AsyncMock(return_value=False)
        provider._get_client()
        assert provider._client is not None
        provider._client.stream = MagicMock(return_value=cm)  # type: ignore[method-assign]

        prov, chunks = await provider.forward_streaming_request(stream_req)

        assert prov.is_streaming is True
        assert prov.reasoning_tokens == 888
        assert prov.input_tokens == 3
        assert prov.output_tokens == 7
        assert prov.ttft_ms is not None
        assert len(chunks) >= 2
