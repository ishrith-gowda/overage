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
