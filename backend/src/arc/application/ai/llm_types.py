"""LLM adapter contracts and DTOs.

This module intentionally has no imports from concrete provider adapters.
Provider implementations depend on these contracts, while factory modules can
depend on provider implementations without creating import cycles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator

from arc.domain.errors import AppError


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """A single message in a chat conversation."""

    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("system", "user", "assistant"):
            raise AppError(f"Invalid role: {self.role!r}")
        if not self.content or not self.content.strip():
            raise AppError("Message content cannot be empty")


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """The result returned from a non-streaming chat request."""

    content: str
    model: str
    usage: dict = field(default_factory=dict)
    finish_reason: str = "stop"


@dataclass
class StreamResult:
    """Metadata collected after a streaming call completes."""

    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)
    model: str = ""


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
        """Stream a chat response and collect metadata in *result*."""
        result = StreamResult()

        async def _wrap():
            token_count = 0
            async for chunk in self.chat_stream(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
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
        """Call LLM with tool definitions."""
        raise NotImplementedError("Subclass must implement chat_with_tools")

    @property
    def provider_type(self) -> str:
        """Return 'anthropic' or 'openai' to identify the backend."""
        return "unknown"

    @abstractmethod
    async def close(self) -> None:
        """Release underlying HTTP resources."""

    async def list_models(self) -> list[str]:
        """拉取该 provider 可用模型清单 (v6.20 L3, verify/list_models 用)。

        OpenAI 兼容走 client.models.list() (免费不计费, 顺带验 key);
        Anthropic 官方无 list API, 子类返静态建议 (诚实降级, 不探活)。
        子类须 override, 默认 raise NotImplementedError。
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support list_models"
        )

    async def verify(self) -> None:
        """探活凭证有效性 (v6.20 L3, 成功不抛, 失败抛异常由 service 捕获分类)。

        OpenAI 兼容走 models.list(); Anthropic 走 1-token messages.create。
        子类须 override, 默认 raise NotImplementedError。
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support verify"
        )
