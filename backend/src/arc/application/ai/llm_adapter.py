"""Unified LLM adapter — base classes, data types, and factory.

Concrete adapters live in sibling modules:
- ``openai_adapter.py`` — OpenAI / DeepSeek
- ``anthropic_adapter.py`` — Anthropic Claude

This module re-exports them so existing ``from arc.application.ai.llm_adapter
import OpenAIAdapter`` continues to work.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """A single message in a chat conversation."""

    role: str  # system | user | assistant
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("system", "user", "assistant"):
            raise ValueError(f"Invalid role: {self.role!r}")
        if not self.content or not self.content.strip():
            raise ValueError("Message content cannot be empty")


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """The result returned from a non-streaming chat request."""

    content: str
    model: str
    usage: dict = field(default_factory=dict)  # prompt_tokens, completion_tokens
    finish_reason: str = "stop"  # stop | length | content_filter | error


@dataclass
class StreamResult:
    """Accumulated metadata collected after a streaming call completes.

    The caller iterates ``chat_stream`` to get text deltas, then reads this
    object (returned via ``chat_stream_with_result``) for the stop signal.
    """

    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)
    model: str = ""


# ---------------------------------------------------------------------------
# Abstract adapter
# ---------------------------------------------------------------------------


class LLMAdapter(ABC):
    """Abstract interface that all LLM backends must implement."""

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat request and return the full response."""

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream a chat response, yielding content deltas as they arrive."""

    async def chat_stream_with_result(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[AsyncIterator[str], StreamResult]:
        """Stream a chat response and collect metadata in *result*.

        Returns ``(async_iterator, result)``.  The caller iterates the
        iterator to get deltas; once the iterator is exhausted, ``result``
        is populated with ``finish_reason`` and ``usage``.  Default
        implementation wraps ``chat_stream`` with heuristic detection —
        subclasses override for native support.
        """
        result = StreamResult()

        async def _wrap():
            token_count = 0
            async for chunk in self.chat_stream(
                messages, temperature=temperature, max_tokens=max_tokens
            ):
                token_count += 1
                yield chunk
            result.usage = {"completion_tokens_approx": token_count}

        return _wrap(), result

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        system: str = "",
        max_tokens: int = 16384,
    ) -> dict:
        """Call LLM with tool definitions. Returns raw API response as dict.

        Subclasses must override. The format of messages, tools, and response
        is provider-specific — callers should dispatch based on provider_type.
        """
        raise NotImplementedError("Subclass must implement chat_with_tools")

    @property
    def provider_type(self) -> str:
        """Return 'anthropic' or 'openai' to identify the backend."""
        return "unknown"

    @abstractmethod
    async def close(self) -> None:
        """Release underlying HTTP resources."""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_llm_adapter() -> LLMAdapter:
    """Create an :class:`LLMAdapter` based on ``settings.llm_provider``.

    Supported providers: ``openai``, ``anthropic``, ``deepseek``.
    Uses lazy imports to avoid requiring all provider SDKs at startup.
    """
    from arc.config import settings

    provider = settings.llm_provider.lower()

    if provider == "openai":
        from arc.application.ai.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
    if provider == "anthropic":
        from arc.application.ai.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            base_url=settings.anthropic_base_url,
            embedding_api_key=settings.openai_api_key,
            embedding_base_url=settings.openai_base_url,
        )
    if provider == "deepseek":
        from arc.application.ai.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
        )

    raise ValueError(f"Unsupported LLM provider: {provider!r}")


# ---------------------------------------------------------------------------
# Re-exports for backward compatibility
# ---------------------------------------------------------------------------
# Existing code does ``from arc.application.ai.llm_adapter import OpenAIAdapter``
# so we re-export here to avoid breaking any import paths.

from arc.application.ai.anthropic_adapter import AnthropicAdapter  # noqa: E402, F401
from arc.application.ai.openai_adapter import OpenAIAdapter  # noqa: E402, F401

__all__ = [
    "LLMAdapter",
    "LLMMessage",
    "LLMResponse",
    "StreamResult",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "create_llm_adapter",
]
