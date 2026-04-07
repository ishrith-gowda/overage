"""Overage SDK client — route LLM calls through the Overage audit proxy."""

from __future__ import annotations

from typing import Any

import httpx


class OverageClient:
    """Thin helper to point OpenAI / Anthropic SDKs at the Overage proxy.

    The proxy expects your **Overage** API key on every request via ``X-API-Key``.
    Provider keys (OpenAI / Anthropic) are passed through by each SDK as usual.

    Args:
        api_key: Your Overage API key (``ovg_live_...``).
        proxy_url: Base URL of the Overage proxy (default: production hostname).
    """

    def __init__(self, api_key: str, proxy_url: str = "https://api.overage.dev") -> None:
        self.api_key = api_key
        self.proxy_url = proxy_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self.proxy_url,
            headers={"X-API-Key": self.api_key},
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Provider patching
    # ------------------------------------------------------------------

    def patch_openai(self, client: Any) -> Any:
        """Point an OpenAI SDK client at ``/v1/proxy/openai`` with Overage auth.

        Args:
            client: An ``openai.OpenAI`` (or ``AsyncOpenAI``) instance.

        Returns:
            A new client configured for the proxy (``with_options`` / ``copy``).
        """
        copy_fn = getattr(client, "with_options", None) or getattr(client, "copy", None)
        if copy_fn is None:
            msg = "OpenAI client must support with_options() or copy()"
            raise TypeError(msg)
        return copy_fn(
            base_url=f"{self.proxy_url}/v1/proxy/openai",
            default_headers={"X-API-Key": self.api_key},
        )

    def patch_anthropic(self, client: Any) -> Any:
        """Point an Anthropic SDK client at ``/v1/proxy/anthropic`` with Overage auth.

        Args:
            client: An ``anthropic.Anthropic`` (or ``AsyncAnthropic``) instance.

        Returns:
            A new client configured for the proxy.
        """
        copy_fn = getattr(client, "with_options", None) or getattr(client, "copy", None)
        if copy_fn is None:
            msg = "Anthropic client must support with_options() or copy()"
            raise TypeError(msg)
        return copy_fn(
            base_url=f"{self.proxy_url}/v1/proxy/anthropic",
            default_headers={"X-API-Key": self.api_key},
        )

    # ------------------------------------------------------------------
    # Overage management API
    # ------------------------------------------------------------------

    def get_summary(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        """Fetch aggregate summary; optional ``group_by`` for per-group breakdown.

        Args:
            start_date: Optional ISO date (inclusive).
            end_date: Optional ISO date (inclusive).
            group_by: Optional ``provider``, ``model``, or ``provider_model``.

        Returns:
            Either flat summary fields or ``{"overall": ..., "groups": [...]}``.
        """
        params: dict[str, str] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if group_by:
            params["group_by"] = group_by

        resp = self._http.get("/v1/summary", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_calls(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """Fetch recorded LLM call logs.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip for pagination.

        Returns:
            A dict containing call rows and pagination metadata.
        """
        resp = self._http.get(
            "/v1/calls",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return resp.json()

    def get_alerts(self, status: str = "active") -> dict[str, Any]:
        """List discrepancy alerts for the authenticated user.

        Args:
            status: ``active``, ``acknowledged``, ``resolved``, or ``all``.

        Returns:
            ``{"alerts": [...], "total": n}``.
        """
        resp = self._http.get("/v1/alerts", params={"status": status})
        resp.raise_for_status()
        return resp.json()

    def acknowledge_alert(self, alert_id: int) -> dict[str, Any]:
        """Acknowledge a discrepancy alert (idempotent).

        Args:
            alert_id: Database id of the alert row.

        Returns:
            Serialized ``DiscrepancyAlert`` after update.
        """
        resp = self._http.post(f"/v1/alerts/{alert_id}/acknowledge")
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
