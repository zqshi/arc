"""Unified LLM adapter supporting OpenAI, Anthropic, and DeepSeek providers.

Each provider uses its native SDK. DeepSeek reuses the OpenAI adapter since it
exposes an OpenAI-compatible API with a different ``base_url``.
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
# OpenAI / DeepSeek adapter (compatible API)
# ---------------------------------------------------------------------------


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI-compatible APIs (also used by DeepSeek)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._model = model
        # Lazy import so the module is loadable even when openai is not installed.
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # -- chat -----------------------------------------------------------------

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=formatted,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            logger.error("OpenAI chat failed: %s", exc)
            raise

        choice = resp.choices[0]
        usage = {}
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            }
        return LLMResponse(
            content=choice.message.content or "",
            model=resp.model,
            usage=usage,
        )

    # -- stream ---------------------------------------------------------------

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=formatted,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
        except Exception as exc:
            logger.error("OpenAI stream failed: %s", exc)
            raise

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    async def chat_stream_with_result(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[AsyncIterator[str], StreamResult]:
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        result = StreamResult(model=self._model)

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=formatted,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
        except Exception as exc:
            logger.error("OpenAI stream failed: %s", exc)
            raise

        async def _iterate():
            token_count = 0
            async for chunk in stream:
                if chunk.usage:
                    result.usage = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                    }
                choice = chunk.choices[0] if chunk.choices else None
                if choice and choice.finish_reason:
                    result.finish_reason = choice.finish_reason
                if choice and choice.delta and choice.delta.content:
                    token_count += 1
                    yield choice.delta.content
            if not result.usage:
                result.usage = {"completion_tokens_approx": token_count}

        return _iterate(), result

    # -- embed ----------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        try:
            resp = await self._client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return resp.data[0].embedding
        except Exception as exc:
            logger.warning("OpenAI embed failed: %s, using local model", exc)
            import asyncio

            from arc.application.ai.local_embedding import embed_local

            return await asyncio.to_thread(embed_local, text)

    # -- lifecycle ------------------------------------------------------------

    @property
    def provider_type(self) -> str:
        return "openai"

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        system: str = "",
        max_tokens: int = 16384,
    ) -> dict:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            tools=tools,
        )
        return {
            "type": "openai",
            "response": response,
            "usage": {
                "input": response.usage.prompt_tokens if response.usage else 0,
                "output": response.usage.completion_tokens if response.usage else 0,
            },
        }

    async def close(self) -> None:
        await self._client.close()


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------


class AnthropicAdapter(LLMAdapter):
    """Adapter for the Anthropic Messages API.

    Embedding uses OpenAI text-embedding-3-small as Anthropic has no native
    embedding endpoint.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "",
        embedding_api_key: str = "",
        embedding_base_url: str = "https://api.openai.com/v1",
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._model = model
        self._embedding_api_key = embedding_api_key
        self._embedding_base_url = embedding_base_url
        from anthropic import AsyncAnthropic

        client_kwargs: dict = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = AsyncAnthropic(**client_kwargs)
        self._embed_client = None

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _split_system(messages: list[LLMMessage]) -> tuple[str, list[dict]]:
        """Anthropic requires ``system`` as a top-level param, not in messages."""
        system_parts: list[str] = []
        chat_msgs: list[dict] = []
        for m in messages:
            if m.role == "system":
                system_parts.append(m.content)
            else:
                chat_msgs.append({"role": m.role, "content": m.content})
        return "\n\n".join(system_parts), chat_msgs

    # -- chat -----------------------------------------------------------------

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        system_text, chat_msgs = self._split_system(messages)
        kwargs: dict = {
            "model": self._model,
            "messages": chat_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_text:
            kwargs["system"] = system_text

        try:
            resp = await self._client.messages.create(**kwargs)
        except Exception as exc:
            logger.error("Anthropic chat failed: %s", exc)
            raise

        content = ""
        for block in resp.content:
            if block.type == "text":
                content += block.text

        usage = {}
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.input_tokens,
                "completion_tokens": resp.usage.output_tokens,
            }
        return LLMResponse(content=content, model=resp.model, usage=usage)

    # -- stream ---------------------------------------------------------------

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        system_text, chat_msgs = self._split_system(messages)
        kwargs: dict = {
            "model": self._model,
            "messages": chat_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_text:
            kwargs["system"] = system_text

        try:
            stream = self._client.messages.stream(**kwargs)
        except Exception as exc:
            logger.error("Anthropic stream failed: %s", exc)
            raise

        async with stream as s:
            async for text in s.text_stream:
                yield text

    async def chat_stream_with_result(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[AsyncIterator[str], StreamResult]:
        system_text, chat_msgs = self._split_system(messages)
        result = StreamResult(model=self._model)
        kwargs: dict = {
            "model": self._model,
            "messages": chat_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_text:
            kwargs["system"] = system_text

        try:
            stream = self._client.messages.stream(**kwargs)
        except Exception as exc:
            logger.error("Anthropic stream failed: %s", exc)
            raise

        async def _iterate():
            async with stream as s:
                async for text in s.text_stream:
                    yield text
                response = await s.get_final_message()
                result.finish_reason = (
                    "length" if response.stop_reason == "max_tokens" else "stop"
                )
                if response.usage:
                    result.usage = {
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                    }

        return _iterate(), result

    # -- embed ----------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        if self._embedding_api_key:
            if self._embed_client is None:
                from openai import AsyncOpenAI

                self._embed_client = AsyncOpenAI(
                    api_key=self._embedding_api_key,
                    base_url=self._embedding_base_url,
                )
            try:
                resp = await self._embed_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text,
                )
                return resp.data[0].embedding
            except Exception as exc:
                logger.warning("OpenAI embedding fallback failed: %s, using local model", exc)

        import asyncio

        from arc.application.ai.local_embedding import embed_local

        return await asyncio.to_thread(embed_local, text)

    # -- lifecycle ------------------------------------------------------------

    @property
    def provider_type(self) -> str:
        return "anthropic"

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        system: str = "",
        max_tokens: int = 16384,
    ) -> dict:
        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "tools": tools,
        }
        if system:
            kwargs["system"] = system
        response = await self._client.messages.create(**kwargs)
        usage_input = response.usage.input_tokens if response.usage else 0
        usage_output = response.usage.output_tokens if response.usage else 0
        return {
            "type": "anthropic",
            "content": response.content,
            "stop_reason": response.stop_reason,
            "usage": {"input": usage_input, "output": usage_output},
        }

    async def close(self) -> None:
        await self._client.close()
        if self._embed_client:
            await self._embed_client.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_llm_adapter() -> LLMAdapter:
    """Create an :class:`LLMAdapter` based on ``settings.llm_provider``.

    Supported providers: ``openai``, ``anthropic``, ``deepseek``.
    """
    from arc.config import settings

    provider = settings.llm_provider.lower()

    if provider == "openai":
        return OpenAIAdapter(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        )
    if provider == "anthropic":
        return AnthropicAdapter(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            base_url=settings.anthropic_base_url,
            embedding_api_key=settings.openai_api_key,
            embedding_base_url=settings.openai_base_url,
        )
    if provider == "deepseek":
        return OpenAIAdapter(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
        )

    raise ValueError(f"Unsupported LLM provider: {provider!r}")
