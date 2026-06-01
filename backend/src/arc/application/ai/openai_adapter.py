"""OpenAI / DeepSeek adapter — OpenAI-compatible chat, streaming, and embedding."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from arc.application.ai.llm_adapter import LLMAdapter, LLMMessage, LLMResponse, StreamResult

logger = logging.getLogger(__name__)


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

    # -- tools ----------------------------------------------------------------

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
            parallel_tool_calls=True,
        )
        return {
            "type": "openai",
            "response": response,
            "usage": {
                "input": response.usage.prompt_tokens if response.usage else 0,
                "output": response.usage.completion_tokens if response.usage else 0,
            },
        }

    # -- lifecycle ------------------------------------------------------------

    async def close(self) -> None:
        await self._client.close()
