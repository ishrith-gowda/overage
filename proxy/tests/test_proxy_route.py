"""Tests for POST /v1/proxy/{provider} — core proxy forwarding path.

Uses mocked LLM providers so no real API keys or network calls are required.
Reference: PRD.md Story 1 (Route OpenAI API Calls Through Proxy).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from proxy.providers.base import ProviderResponse

if TYPE_CHECKING:
    import httpx


def _assert_overage_proxy_headers(response: httpx.Response, *, streaming: bool = False) -> None:
    """Shared assertions for Overage proxy response headers (Phase 1.7 / 1.12)."""
    rid = response.headers.get("X-Overage-Request-Id")
    assert rid is not None
    assert len(rid) > 0
    lat = response.headers.get("X-Overage-Latency-Added-Ms")
    assert lat is not None
    if streaming:
        assert lat == "0"
    else:
        assert float(lat) >= 0.0


class TestProxyAuth:
    """Authentication requirements for the proxy route."""

    @pytest.mark.asyncio
    async def test_proxy_requires_api_key(self, client: httpx.AsyncClient) -> None:
        """POST /v1/proxy/openai without X-API-Key returns 401."""
        response = await client.post(
            "/v1/proxy/openai",
            json={"model": "o3", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 401


class TestProxyOpenAINonStreaming:
    """Non-streaming OpenAI proxy with mocked upstream."""

    @pytest.mark.asyncio
    async def test_proxy_openai_returns_upstream_json_body(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        mock_openai_response: Any,
    ) -> None:
        """Proxied response body matches the upstream JSON (mocked provider)."""
        raw = mock_openai_response(model="o3", reasoning_tokens=10000)
        prov_response = ProviderResponse(
            provider="openai",
            model="o3",
            raw_response=raw,
            raw_usage=raw["usage"],
            input_tokens=100,
            output_tokens=1500,
            reasoning_tokens=10000,
            total_latency_ms=42.5,
            ttft_ms=None,
            status_code=200,
            is_streaming=False,
        )
        mock_provider = AsyncMock()
        mock_provider.forward_request = AsyncMock(return_value=prov_response)

        with (
            patch("proxy.api.routes.provider_registry.get", return_value=mock_provider),
            patch("proxy.api.routes._record_and_estimate", new=AsyncMock()),
        ):
            response = await client.post(
                "/v1/proxy/openai",
                headers={
                    "X-API-Key": test_api_key,
                    "Authorization": "Bearer sk-test-key",
                },
                json={
                    "model": "o3",
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "o3"
        assert body["usage"]["completion_tokens_details"]["reasoning_tokens"] == 10000
        _assert_overage_proxy_headers(response, streaming=False)
        mock_provider.forward_request.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_proxy_openai_chat_completions_path_matches_sdk(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        mock_openai_response: Any,
    ) -> None:
        """Alias path matches OpenAI Python SDK URL pattern (base_url + /chat/completions)."""
        raw = mock_openai_response(model="o3-mini")
        prov_response = ProviderResponse(
            provider="openai",
            model="o3-mini",
            raw_response=raw,
            raw_usage=raw["usage"],
            input_tokens=50,
            output_tokens=100,
            reasoning_tokens=500,
            total_latency_ms=10.0,
            ttft_ms=None,
            status_code=200,
            is_streaming=False,
        )
        mock_provider = AsyncMock()
        mock_provider.forward_request = AsyncMock(return_value=prov_response)

        with (
            patch("proxy.api.routes.provider_registry.get", return_value=mock_provider),
            patch("proxy.api.routes._record_and_estimate", new=AsyncMock()),
        ):
            response = await client.post(
                "/v1/proxy/openai/chat/completions",
                headers={
                    "X-API-Key": test_api_key,
                    "Authorization": "Bearer sk-test-key",
                },
                json={
                    "model": "o3-mini",
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False,
                },
            )

        assert response.status_code == 200
        assert response.json()["model"] == "o3-mini"
        _assert_overage_proxy_headers(response, streaming=False)


class TestProxyAnthropicNonStreaming:
    """Non-streaming Anthropic proxy with mocked upstream (Messages API shape)."""

    @pytest.mark.asyncio
    async def test_proxy_anthropic_v1_messages_path_matches_sdk(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        mock_anthropic_response: Any,
    ) -> None:
        """Alias path matches Anthropic Python SDK (base_url + /v1/messages)."""
        raw = mock_anthropic_response(
            model="claude-sonnet-4-20250514",
            thinking_tokens=1200,
        )
        prov_response = ProviderResponse(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            raw_response=raw,
            raw_usage=raw["usage"],
            input_tokens=raw["usage"]["input_tokens"],
            output_tokens=raw["usage"]["output_tokens"],
            reasoning_tokens=1200,
            total_latency_ms=88.0,
            ttft_ms=None,
            status_code=200,
            is_streaming=False,
        )
        mock_provider = AsyncMock()
        mock_provider.forward_request = AsyncMock(return_value=prov_response)

        with (
            patch("proxy.api.routes.provider_registry.get", return_value=mock_provider),
            patch("proxy.api.routes._record_and_estimate", new=AsyncMock()),
        ):
            response = await client.post(
                "/v1/proxy/anthropic/v1/messages",
                headers={
                    "X-API-Key": test_api_key,
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 256,
                    "messages": [{"role": "user", "content": "Hello"}],
                    "stream": False,
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "claude-sonnet-4-20250514"
        assert body["usage"]["thinking_tokens"] == 1200
        _assert_overage_proxy_headers(response, streaming=False)
        mock_provider.forward_request.assert_awaited_once()


class TestProxyAnthropicStreaming:
    """Streaming Anthropic proxy path (Phase 2) with mocked upstream."""

    @pytest.mark.asyncio
    async def test_proxy_anthropic_streaming_returns_sse_with_overage_headers(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """``StreamingResponse`` echoes chunks and Overage headers (mocked adapter)."""
        prov_response = ProviderResponse(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            raw_response={},
            raw_usage={"input_tokens": 1, "output_tokens": 2, "thinking_tokens": 0},
            input_tokens=1,
            output_tokens=2,
            reasoning_tokens=0,
            total_latency_ms=4.0,
            ttft_ms=0.8,
            status_code=200,
            is_streaming=True,
        )
        chunks = [b"event: message_start\ndata: {}\n\n", b"event: message_stop\ndata: {}\n\n"]
        mock_provider = AsyncMock()
        mock_provider.forward_streaming_request = AsyncMock(return_value=(prov_response, chunks))

        with (
            patch("proxy.api.routes.provider_registry.get", return_value=mock_provider),
            patch("proxy.api.routes._record_and_estimate", new=AsyncMock()),
        ):
            response = await client.post(
                "/v1/proxy/anthropic/v1/messages",
                headers={
                    "X-API-Key": test_api_key,
                    "x-api-key": "sk-ant-test",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 128,
                    "messages": [{"role": "user", "content": "stream"}],
                    "stream": True,
                },
            )

        assert response.status_code == 200
        assert "event-stream" in (response.headers.get("content-type") or "").lower()
        _assert_overage_proxy_headers(response, streaming=True)
        assert b"message_start" in response.content or b"data:" in response.content
        mock_provider.forward_streaming_request.assert_awaited_once()


class TestProxyErrors:
    """Error responses for invalid proxy targets."""

    @pytest.mark.asyncio
    async def test_proxy_unknown_provider_returns_error(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """Unknown provider name returns an error response (not 200)."""
        response = await client.post(
            "/v1/proxy/not-a-provider",
            headers={
                "X-API-Key": test_api_key,
                "Authorization": "Bearer sk-test",
            },
            json={"model": "x", "messages": []},
        )
        assert response.status_code != 200


class TestProxyOpenAIStreaming:
    """Streaming OpenAI proxy path (Phase 1.6) with mocked upstream."""

    @pytest.mark.asyncio
    async def test_proxy_openai_streaming_returns_sse_with_overage_headers(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
    ) -> None:
        """StreamingResponse echoes SSE chunks and Overage latency headers (proxy adds 0 ms)."""
        prov_response = ProviderResponse(
            provider="openai",
            model="o3",
            raw_response={},
            raw_usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            input_tokens=1,
            output_tokens=2,
            reasoning_tokens=0,
            total_latency_ms=5.0,
            ttft_ms=1.2,
            status_code=200,
            is_streaming=True,
        )
        chunks = [b'data: {"chunk":true}\n\n', b"data: [DONE]\n\n"]
        mock_provider = AsyncMock()
        mock_provider.forward_streaming_request = AsyncMock(return_value=(prov_response, chunks))

        with (
            patch("proxy.api.routes.provider_registry.get", return_value=mock_provider),
            patch("proxy.api.routes._record_and_estimate", new=AsyncMock()),
        ):
            response = await client.post(
                "/v1/proxy/openai",
                headers={
                    "X-API-Key": test_api_key,
                    "Authorization": "Bearer sk-test",
                },
                json={
                    "model": "o3",
                    "messages": [{"role": "user", "content": "stream me"}],
                    "stream": True,
                },
            )

        assert response.status_code == 200
        assert "event-stream" in (response.headers.get("content-type") or "")
        _assert_overage_proxy_headers(response, streaming=True)
        body = response.content
        assert b"data:" in body
        mock_provider.forward_streaming_request.assert_awaited_once()


class TestProxyBackgroundPersistence:
    """Proxy → ``_record_and_estimate`` → ``GET /v1/calls`` (Phase 1.8) without mocking the task."""

    @pytest.mark.asyncio
    async def test_proxy_openai_nonstreaming_persists_call_visible_in_list(
        self,
        client: httpx.AsyncClient,
        test_api_key: str,
        mock_openai_response: Any,
    ) -> None:
        """Background task writes ``APICallLog`` rows visible to the same test database."""
        import asyncio

        from proxy.tests.conftest import async_sqlite_session_factory

        raw = mock_openai_response(model="o3", reasoning_tokens=42)
        prov_response = ProviderResponse(
            provider="openai",
            model="o3",
            raw_response=raw,
            raw_usage=raw["usage"],
            input_tokens=10,
            output_tokens=20,
            reasoning_tokens=42,
            total_latency_ms=12.3,
            ttft_ms=None,
            status_code=200,
            is_streaming=False,
        )
        mock_provider = AsyncMock()
        mock_provider.forward_request = AsyncMock(return_value=prov_response)

        session_factory = async_sqlite_session_factory()
        with (
            patch("proxy.api.routes.provider_registry.get", return_value=mock_provider),
            patch("proxy.api.routes.get_session_factory", return_value=session_factory),
        ):
            post_r = await client.post(
                "/v1/proxy/openai",
                headers={
                    "X-API-Key": test_api_key,
                    "Authorization": "Bearer sk-test",
                },
                json={
                    "model": "o3",
                    "messages": [{"role": "user", "content": "persist"}],
                    "stream": False,
                },
            )

        assert post_r.status_code == 200
        _assert_overage_proxy_headers(post_r, streaming=False)

        await asyncio.sleep(0.05)

        list_r = await client.get("/v1/calls", headers={"X-API-Key": test_api_key})
        assert list_r.status_code == 200
        payload = list_r.json()
        assert payload["total"] >= 1
        first = payload["calls"][0]
        assert first["provider"] == "openai"
        assert first["model"] == "o3"
        assert first["reported_reasoning_tokens"] == 42
