"""Application-level LLM adapter manager.

Provides a shared adapter instance (with resilience) to avoid creating
new HTTP clients on every WebSocket message. Also emits structured trace
events for every LLM call.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from arc.application.ai.llm_adapter import LLMAdapter, LLMMessage, LLMResponse
from arc.application.ai.resilience import create_resilient_adapter

logger = logging.getLogger(__name__)


class TracingAdapter(LLMAdapter):
    """Wraps an adapter to emit structured trace logs for each call."""

    def __init__(self, inner: LLMAdapter):
        self._inner = inner

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        trace_id = str(uuid.uuid4())[:8]
        msg_count = len(messages)
        start = time.perf_counter()

        try:
            response = await self._inner.chat(
                messages, temperature=temperature, max_tokens=max_tokens
            )
            elapsed = time.perf_counter() - start
            logger.info(
                "llm.chat",
                extra={
                    "trace_id": trace_id,
                    "model": response.model,
                    "messages": msg_count,
                    "prompt_tokens": response.usage.get("prompt_tokens", 0),
                    "completion_tokens": response.usage.get("completion_tokens", 0),
                    "latency_ms": int(elapsed * 1000),
                    "temperature": temperature,
                },
            )
            return response
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error(
                "llm.chat.error",
                extra={
                    "trace_id": trace_id,
                    "messages": msg_count,
                    "latency_ms": int(elapsed * 1000),
                    "error": str(exc),
                },
            )
            raise

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        trace_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        token_count = 0

        try:
            async for chunk in self._inner.chat_stream(
                messages, temperature=temperature, max_tokens=max_tokens
            ):
                token_count += 1
                yield chunk
        finally:
            elapsed = time.perf_counter() - start
            logger.info(
                "llm.stream",
                extra={
                    "trace_id": trace_id,
                    "messages": len(messages),
                    "chunks": token_count,
                    "latency_ms": int(elapsed * 1000),
                },
            )

    async def embed(self, text: str) -> list[float]:
        start = time.perf_counter()
        try:
            result = await self._inner.embed(text)
            elapsed = time.perf_counter() - start
            logger.info(
                "llm.embed",
                extra={
                    "text_length": len(text),
                    "vector_dim": len(result),
                    "latency_ms": int(elapsed * 1000),
                },
            )
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error(
                "llm.embed.error",
                extra={
                    "text_length": len(text),
                    "latency_ms": int(elapsed * 1000),
                    "error": str(exc),
                },
            )
            raise

    async def close(self) -> None:
        await self._inner.close()


class AdapterPool:
    """Manages a shared resilient+tracing adapter instance.

    Usage:
        async with adapter_pool.acquire() as adapter:
            response = await adapter.chat(messages)
    """

    def __init__(self):
        self._adapter: TracingAdapter | None = None

    def _ensure_adapter(self) -> TracingAdapter:
        if self._adapter is None:
            inner = create_resilient_adapter()
            self._adapter = TracingAdapter(inner)
        return self._adapter

    @asynccontextmanager
    async def acquire(self):
        adapter = self._ensure_adapter()
        yield adapter

    async def shutdown(self) -> None:
        if self._adapter:
            await self._adapter.close()
            self._adapter = None


adapter_pool = AdapterPool()
