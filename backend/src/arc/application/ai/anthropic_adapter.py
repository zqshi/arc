"""Anthropic adapter — Claude Messages API chat, streaming, and embedding."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from arc.application.ai.llm_types import LLMAdapter, LLMMessage, LLMResponse, StreamResult

logger = logging.getLogger(__name__)


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
            kwargs["system"] = [
                {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
            ]

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
            kwargs["system"] = [
                {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
            ]

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
            kwargs["system"] = [
                {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
            ]

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

    # -- tools ----------------------------------------------------------------

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
            kwargs["system"] = [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ]
        response = await self._client.messages.create(**kwargs)
        usage_input = response.usage.input_tokens if response.usage else 0
        usage_output = response.usage.output_tokens if response.usage else 0
        return {
            "type": "anthropic",
            "content": response.content,
            "stop_reason": response.stop_reason,
            "usage": {"input": usage_input, "output": usage_output},
        }

    # -- lifecycle ------------------------------------------------------------

    async def close(self) -> None:
        await self._client.close()
        if self._embed_client:
            await self._embed_client.close()
