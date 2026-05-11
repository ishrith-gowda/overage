"""Validate operator-configured proxy base URL for dashboard HTTP clients."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse


def normalized_proxy_base_url(url: str) -> str:
    """Return ``scheme://netloc`` suitable for ``httpx.Client(base_url=...)``.

    Accepts only ``http`` or ``https`` with a hostname, rejects embedded
    credentials, and drops path, query, and fragment so callers use fixed
    ``/v1/...`` paths (reduces path-based request manipulation).

    Args:
        url: Raw base URL from the Streamlit sidebar.

    Returns:
        Normalized origin without a trailing slash.

    Raises:
        ValueError: If ``url`` is not a usable HTTP(S) origin.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        msg = "proxy URL must use http or https"
        raise ValueError(msg)
    if parsed.hostname is None or parsed.hostname == "":
        msg = "proxy URL must include a hostname"
        raise ValueError(msg)
    if parsed.username is not None or parsed.password is not None:
        msg = "proxy URL must not embed credentials; use the API key field"
        raise ValueError(msg)
    origin = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    return origin.rstrip("/")
