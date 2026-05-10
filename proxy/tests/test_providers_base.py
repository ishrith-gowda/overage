"""Tests for ``LLMProvider`` / registry contracts (Phase 1 ledger alignment).

Reference: ``docs/ROADMAP.md`` Phase 1.1 and 1.3.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from proxy.exceptions import ProviderError
from proxy.providers.base import LLMProvider, ProviderRequest, ProviderResponse, provider_registry
from proxy.providers.openai import OpenAIProvider

if TYPE_CHECKING:
    import httpx


class TestLLMProviderABC:
    """Incomplete ``LLMProvider`` subclasses must fail at instantiation."""

    def test_incomplete_subclass_raises_type_error_on_instantiation(self) -> None:
        """Forgetting abstract methods raises ``TypeError`` when constructing (not at import)."""

        class Broken(LLMProvider):
            pass

        with pytest.raises(TypeError, match=r"abstract|Can't instantiate"):
            _ = Broken()  # type: ignore[abstract]


class TestProviderRegistry:
    """``provider_registry.get`` behaviour for Phase 1.3."""

    @pytest.mark.asyncio
    async def test_get_openai_returns_openai_provider(self, client: httpx.AsyncClient) -> None:
        """Registered ``openai`` resolves to ``OpenAIProvider`` (requires app lifespan)."""
        _ = client
        p = provider_registry.get("openai")
        assert isinstance(p, OpenAIProvider)

    def test_get_unknown_raises_provider_error(self) -> None:
        """Unknown provider name raises ``ProviderError`` (not Pydantic ``ValidationError``)."""
        with pytest.raises(ProviderError, match="Unknown provider"):
            provider_registry.get("not-a-real-provider-xyz")


@pytest.mark.asyncio
async def test_llm_provider_complete_subclass_instantiates() -> None:
    """A fully implemented stub can be constructed (sanity check for ABC wiring)."""

    class Stub(LLMProvider):
        def get_provider_name(self) -> str:
            return "stub"

        async def forward_request(self, request: ProviderRequest) -> ProviderResponse:
            return ProviderResponse(
                provider="stub",
                model=request.model,
                raw_response={},
                raw_usage={},
            )

        async def forward_streaming_request(
            self, request: ProviderRequest
        ) -> tuple[ProviderResponse, list[bytes]]:
            return (
                ProviderResponse(
                    provider="stub",
                    model=request.model,
                    raw_response={},
                    raw_usage={},
                    is_streaming=True,
                ),
                [],
            )

        def extract_reasoning_tokens(self, raw_usage: dict[str, object]) -> int:
            return 0

    s = Stub()
    assert s.get_provider_name() == "stub"
