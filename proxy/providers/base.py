"""Abstract base class and data structures for LLM provider adapters.

Every provider (OpenAI, Anthropic, Gemini) implements LLMProvider.
Adding a new provider = one new file implementing this interface.
Reference: INSTRUCTIONS.md Section 12 (Provider Implementation Patterns).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

from proxy.exceptions import ProviderError

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderRequest:
    """Normalized representation of a request to an LLM provider.

    Attributes:
        provider: Provider name (e.g. 'openai', 'anthropic').
        model: Model identifier (e.g. 'o3', 'claude-sonnet-4-20250514').
        messages: The conversation messages (list of dicts).
        raw_body: The raw request body forwarded to the provider.
        stream: Whether the client requested streaming.
        provider_api_key: API key for the upstream provider.
    """

    provider: str
    model: str
    messages: list[dict[str, Any]]
    raw_body: dict[str, Any]
    stream: bool = False
    provider_api_key: str = ""


@dataclass
class ProviderResponse:
    """Normalized response from an LLM provider.

    Attributes:
        provider: Provider name.
        model: Model identifier returned by the provider.
        raw_response: The complete JSON response body.
        raw_usage: The raw usage object from the provider response.
        input_tokens: Provider-reported input/prompt token count.
        output_tokens: Provider-reported output/completion token count.
        reasoning_tokens: Provider-reported reasoning/thinking token count.
        total_latency_ms: Wall-clock time for the full request-response cycle.
        ttft_ms: Time to first token (streaming only; None for non-streaming).
        status_code: HTTP status code from the provider.
        is_streaming: Whether this was a streamed response.
    """

    provider: str
    model: str
    raw_response: dict[str, Any]
    raw_usage: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_latency_ms: float = 0.0
    ttft_ms: float | None = None
    status_code: int = 200
    is_streaming: bool = False


@dataclass
class StreamChunk:
    """A single SSE chunk from a streaming response.

    Attributes:
        raw_bytes: The raw bytes of the SSE event.
        is_final: Whether this is the last chunk (contains usage data).
        usage: Token usage data if this is the final chunk.
    """

    raw_bytes: bytes
    is_final: bool = False
    usage: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Abstract interface for LLM provider adapters.

    To add a new provider:
    1. Create proxy/providers/<name>.py
    2. Subclass LLMProvider and implement all abstract methods
    3. Register in ProviderRegistry below
    4. Add tests in proxy/tests/unit/test_providers/
    """

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the canonical provider name (e.g. 'openai')."""
        ...

    @abstractmethod
    async def forward_request(
        self,
        request: ProviderRequest,
    ) -> ProviderResponse:
        """Forward a non-streaming request to the provider.

        Args:
            request: The normalized provider request.

        Returns:
            The normalized provider response with timing and usage data.

        Raises:
            ProviderTimeoutError: If the provider does not respond in time.
            ProviderAPIError: If the provider returns an error.
        """
        ...

    @abstractmethod
    async def forward_streaming_request(
        self,
        request: ProviderRequest,
    ) -> tuple[ProviderResponse, list[bytes]]:
        """Forward a streaming request to the provider.

        Collects all SSE chunks and extracts usage from the final chunk.

        Args:
            request: The normalized provider request.

        Returns:
            Tuple of (ProviderResponse with usage, list of raw SSE chunk bytes).
        """
        ...

    @abstractmethod
    def extract_reasoning_tokens(self, raw_usage: dict[str, Any]) -> int:
        """Extract the reasoning / thinking token count from raw usage data.

        Args:
            raw_usage: The raw usage object from the provider response.

        Returns:
            The reasoning token count, or 0 if not present.
        """
        ...


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------


class ProviderRegistry:
    """Registry mapping provider names to LLMProvider instances.

    Thread-safe singleton — providers are registered once at startup.
    """

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def register(self, provider: LLMProvider) -> None:
        """Register a provider instance.

        Args:
            provider: The provider to register.
        """
        name = provider.get_provider_name()
        self._providers[name] = provider
        logger.info("provider_registered", provider=name)

    def get(self, name: str) -> LLMProvider:
        """Get a provider by name.

        Args:
            name: The provider name (e.g. 'openai').

        Returns:
            The registered LLMProvider instance.

        Raises:
            ProviderError: If the provider is not registered.
        """
        provider = self._providers.get(name)
        if provider is None:
            available = list(self._providers.keys())
            raise ProviderError(
                message=f"Unknown provider '{name}'. Available: {available}",
                provider=name,
                status_code=400,
            )
        return provider

    @property
    def available_providers(self) -> list[str]:
        """List all registered provider names."""
        return list(self._providers.keys())


# Singleton instance — populated during app startup
provider_registry = ProviderRegistry()
