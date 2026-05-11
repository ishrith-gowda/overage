"""Smoke tests for the ``overage`` SDK client (Phase 4.8).

Uses lightweight fakes so OpenAI / Anthropic packages are not required in CI.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from overage.client import OverageClient


class _FakeSdkClient:
    """Minimal stand-in for OpenAI / Anthropic clients."""

    def __init__(self) -> None:
        self.last_kwargs: dict[str, Any] = {}

    def with_options(self, **kwargs: Any) -> str:
        self.last_kwargs = kwargs
        return "patched-client"


def test_overage_client_uses_proxy_base_and_api_key_header() -> None:
    """Constructor wires httpx with ``X-API-Key`` and stripped proxy URL."""
    with patch("overage.client.httpx.Client") as mock_client_cls:
        OverageClient("ovg_live_unit_test", proxy_url="https://proxy.example/")
        mock_client_cls.assert_called_once()
        kwargs = mock_client_cls.call_args.kwargs
        assert kwargs["base_url"] == "https://proxy.example"
        assert kwargs["headers"] == {"X-API-Key": "ovg_live_unit_test"}
        assert kwargs["timeout"] == 30.0


def test_patch_openai_forwards_proxy_path_and_header() -> None:
    """``patch_openai`` targets ``/v1/proxy/openai`` with Overage auth headers."""
    fake = _FakeSdkClient()
    client = OverageClient("ovg_live_x", proxy_url="http://localhost:8000")
    out = client.patch_openai(fake)
    assert out == "patched-client"
    assert fake.last_kwargs["base_url"] == "http://localhost:8000/v1/proxy/openai"
    assert fake.last_kwargs["default_headers"] == {"X-API-Key": "ovg_live_x"}


def test_patch_anthropic_forwards_proxy_path_and_header() -> None:
    """``patch_anthropic`` targets ``/v1/proxy/anthropic`` with Overage auth headers."""
    fake = _FakeSdkClient()
    client = OverageClient("ovg_live_y", proxy_url="http://127.0.0.1:9")
    out = client.patch_anthropic(fake)
    assert out == "patched-client"
    assert fake.last_kwargs["base_url"] == "http://127.0.0.1:9/v1/proxy/anthropic"
    assert fake.last_kwargs["default_headers"] == {"X-API-Key": "ovg_live_y"}


def test_patch_openai_requires_with_options_or_copy() -> None:
    """Unsupported client objects raise a clear ``TypeError``."""

    class Bad:
        pass

    with pytest.raises(TypeError, match="with_options"):
        OverageClient("ovg_live_z").patch_openai(Bad())
