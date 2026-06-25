"""Application-level LLM adapter manager.

Provides a multi-model adapter pool with concurrency control. Each model key
gets its own resilient + tracing adapter instance, cached for reuse.

Usage:
    async with adapter_pool.acquire() as adapter:       # default model
        response = await adapter.chat(messages)

    async with adapter_pool.acquire_worker() as adapter: # cheap model
        response = await adapter.chat(messages)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from arc.application.ai.llm_adapter import LLMAdapter, LLMMessage, LLMResponse, StreamResult

logger = logging.getLogger(__name__)

_DEFAULT_KEY = "__default__"
_WORKER_KEY = "__worker__"


# ---------------------------------------------------------------------------
# Tracing wrapper (unchanged from original)
# ---------------------------------------------------------------------------


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
                    "messages": len(messages),
                    "prompt_tokens": response.usage.get("prompt_tokens", 0),
                    "completion_tokens": response.usage.get("completion_tokens", 0),
                    "latency_ms": int(elapsed * 1000),
                },
            )
            return response
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error(
                "llm.chat.error",
                extra={
                    "trace_id": trace_id,
                    "messages": len(messages),
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

    async def chat_stream_with_result(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> tuple[AsyncIterator[str], StreamResult]:
        trace_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        inner_iter, result = await self._inner.chat_stream_with_result(
            messages, temperature=temperature, max_tokens=max_tokens
        )

        async def _traced():
            token_count = 0
            try:
                async for chunk in inner_iter:
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
                        "finish_reason": result.finish_reason,
                        "usage": result.usage,
                    },
                )

        return _traced(), result

    async def embed(self, text: str) -> list[float]:
        start = time.perf_counter()
        try:
            vec = await self._inner.embed(text)
            elapsed = time.perf_counter() - start
            logger.info(
                "llm.embed",
                extra={
                    "text_length": len(text),
                    "vector_dim": len(vec),
                    "latency_ms": int(elapsed * 1000),
                },
            )
            return vec
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

    @property
    def provider_type(self) -> str:
        return self._inner.provider_type

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        system: str = "",
        max_tokens: int = 16384,
    ) -> dict:
        trace_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        try:
            result = await self._inner.chat_with_tools(
                messages, tools, system=system, max_tokens=max_tokens
            )
            elapsed = time.perf_counter() - start
            usage = result.get("usage", {})
            logger.info(
                "llm.chat_with_tools",
                extra={
                    "trace_id": trace_id,
                    "messages": len(messages),
                    "tools": len(tools),
                    "input_tokens": usage.get("input", 0),
                    "output_tokens": usage.get("output", 0),
                    "latency_ms": int(elapsed * 1000),
                },
            )
            return result
        except Exception as exc:
            elapsed = time.perf_counter() - start
            logger.error(
                "llm.chat_with_tools.error",
                extra={
                    "trace_id": trace_id,
                    "messages": len(messages),
                    "latency_ms": int(elapsed * 1000),
                    "error": str(exc),
                },
            )
            raise


# ---------------------------------------------------------------------------
# Multi-model adapter pool
# ---------------------------------------------------------------------------


class AdapterPool:
    """Manages a keyed pool of resilient+tracing adapter instances.

    Each model configuration gets its own adapter, cached for reuse.
    A semaphore limits concurrent worker calls to avoid rate-limit storms.

    Usage:
        async with adapter_pool.acquire() as adapter:         # default model
            ...
        async with adapter_pool.acquire_worker() as adapter:  # cheap model
            ...
    """

    def __init__(self) -> None:
        self._adapters: dict[str, TracingAdapter] = {}
        self._semaphore: asyncio.Semaphore | None = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            from arc.config import settings
            self._semaphore = asyncio.Semaphore(settings.max_concurrent_workers)
        return self._semaphore

    def _ensure_adapter(self, key: str = _DEFAULT_KEY) -> TracingAdapter:
        if key not in self._adapters:
            from arc.application.ai.resilience import create_resilient_adapter

            if key == _WORKER_KEY:
                inner = _create_worker_adapter()
            else:
                inner = create_resilient_adapter()
            self._adapters[key] = TracingAdapter(inner)
        return self._adapters[key]

    @asynccontextmanager
    async def acquire(self, model_key: str | None = None):
        """Acquire the default (or specified) adapter.

        ``model_key=None`` uses the main configured model — fully backward
        compatible with all existing call sites.
        """
        key = model_key or _DEFAULT_KEY
        adapter = self._ensure_adapter(key)
        yield adapter

    @asynccontextmanager
    async def acquire_for_project(self, llm_config: dict | None):
        """Acquire an adapter using project-level LLM config.

        If config is None/empty/incomplete, falls back to the global default.
        Project adapters are NOT cached in the pool — they're ephemeral.
        """
        if not llm_config or not llm_config.get("api_key"):
            # No project override — use global
            adapter = self._ensure_adapter(_DEFAULT_KEY)
            yield adapter
            return

        from arc.application.ai.llm_adapter import create_llm_adapter_from_config
        from arc.application.ai.resilience import ResilientAdapter

        inner = create_llm_adapter_from_config(llm_config)
        adapter = TracingAdapter(ResilientAdapter(inner))
        try:
            yield adapter
        finally:
            await inner.close()

    @asynccontextmanager
    async def acquire_worker(self):
        """Acquire a worker adapter (cheap model) with concurrency control.

        If no worker model is configured, falls back to the default model.
        Blocks if the concurrency limit is reached.
        """
        sem = self._get_semaphore()
        async with sem:
            adapter = self._ensure_adapter(_WORKER_KEY)
            yield adapter

    async def shutdown(self) -> None:
        for adapter in self._adapters.values():
            try:
                await adapter.close()
            except Exception as exc:
                logger.warning("Error closing adapter: %s", exc)
        self._adapters.clear()


def _create_worker_adapter():
    """Create an adapter for worker sub-agents, using cheap model if configured."""
    from arc.application.ai.resilience import create_resilient_adapter
    from arc.config import settings

    worker_provider = settings.worker_llm_provider or settings.llm_provider
    worker_model = settings.worker_model

    if not worker_model:
        # No worker model configured — use the same as default
        return create_resilient_adapter()

    # Build a worker-specific adapter with the cheap model
    from arc.application.ai.anthropic_adapter import AnthropicAdapter
    from arc.application.ai.openai_adapter import OpenAIAdapter

    provider = worker_provider.lower()
    if provider == "anthropic":
        inner = AnthropicAdapter(
            api_key=settings.anthropic_api_key,
            model=worker_model,
            base_url=settings.anthropic_base_url,
            embedding_api_key=settings.openai_api_key,
            embedding_base_url=settings.openai_base_url,
        )
    elif provider in ("openai", "deepseek"):
        api_key = settings.deepseek_api_key if provider == "deepseek" else settings.openai_api_key
        base_url = (
            settings.deepseek_base_url if provider == "deepseek"
            else settings.openai_base_url
        )
        inner = OpenAIAdapter(api_key=api_key, model=worker_model, base_url=base_url)
    else:
        return create_resilient_adapter()

    from arc.application.ai.resilience import ResilientAdapter

    return ResilientAdapter(inner)


adapter_pool = AdapterPool()
