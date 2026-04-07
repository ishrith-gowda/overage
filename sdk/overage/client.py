"""Overage SDK client — route LLM calls through the Overage audit proxy."""

from __future__ import annotations

from typing import Any

import httpx


class OverageClient:
    """Thin wrapper that patches OpenAI / Anthropic clients to route through Overage.

    The "1-line change" promise: create an OverageClient, then call
    ``patch_openai`` or ``patch_anthropic`` on your existing provider client.
    All subsequent calls flow through the Overage reverse proxy, which records
    reasoning-token usage so you can audit your bill.

    Args:
        api_key: Your Overage API key.
        proxy_url: Base URL of the Overage proxy (default: ``https://api.overage.dev``).
    """

    def __init__(self, api_key: str, proxy_url: str = "https://api.overage.dev") -> None:
        self.api_key = api_key
        self.proxy_url = proxy_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self.proxy_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Provider patching
    # ------------------------------------------------------------------

    def patch_openai(self, client: Any) -> Any:
        """Patch an OpenAI client to route requests through the Overage proxy.

        Args:
            client: An ``openai.OpenAI`` (or ``AsyncOpenAI``) instance.

        Returns:
            The same client instance, now pointing at the Overage proxy.
        """
        client.base_url = f"{self.proxy_url}/openai/v1"
        client._custom_headers["X-Overage-Key"] = self.api_key
        return client

    def patch_anthropic(self, client: Any) -> Any:
        """Patch an Anthropic client to route requests through the Overage proxy.

        Args:
            client: An ``anthropic.Anthropic`` (or ``AsyncAnthropic``) instance.

        Returns:
            The same client instance, now pointing at the Overage proxy.
        """
        client._base_url = f"{self.proxy_url}/anthropic/v1"
        client._custom_headers["X-Overage-Key"] = self.api_key
        return client

    # ------------------------------------------------------------------
    # Overage management API
    # ------------------------------------------------------------------

    def get_summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch the reasoning-token discrepancy summary.

        Args:
            start_date: Optional ISO-8601 date string (inclusive lower bound).
            end_date: Optional ISO-8601 date string (inclusive upper bound).

        Returns:
            A dict with billing vs. observed token counts and discrepancy info.
        """
        params: dict[str, str] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        resp = self._http.get("/v1/summary", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_calls(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Fetch recorded LLM call logs.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip (for pagination).

        Returns:
            A dict containing a list of call records and pagination metadata.
        """
        resp = self._http.get(
            "/v1/calls",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP transport."""
        self._http.close()

    def __enter__(self) -> OverageClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
