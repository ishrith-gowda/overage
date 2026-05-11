"""Tests for ``dashboard.url_utils`` (shared URL validation for the Streamlit app)."""

from __future__ import annotations

import pytest

from dashboard.url_utils import normalized_proxy_base_url


def test_normalized_proxy_base_url_localhost_no_port_returns_origin() -> None:
    assert normalized_proxy_base_url("http://localhost") == "http://localhost"


def test_normalized_proxy_base_url_strips_path_query_fragment() -> None:
    raw = "https://proxy.example:8443/v1/../evil?x=1#frag"
    assert normalized_proxy_base_url(raw) == "https://proxy.example:8443"


def test_normalized_proxy_base_url_rejects_non_http_scheme() -> None:
    with pytest.raises(ValueError, match="http or https"):
        normalized_proxy_base_url("ftp://example.com")


def test_normalized_proxy_base_url_rejects_missing_host() -> None:
    with pytest.raises(ValueError, match="hostname"):
        normalized_proxy_base_url("http:///v1/summary")


def test_normalized_proxy_base_url_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError, match="credentials"):
        normalized_proxy_base_url("http://user:pass@host:8000/")
