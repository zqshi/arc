"""Unit tests for LLM resilience layer."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from arc.application.ai.llm_adapter import LLMMessage, LLMResponse
from arc.application.ai.resilience import (
    CircuitOpenError,
    ResilientAdapter,
    _CircuitBreaker,
)


def _make_adapter():
    adapter = AsyncMock()
    adapter.chat = AsyncMock()
    adapter.embed = AsyncMock()
    adapter.close = AsyncMock()
    return adapter


class TestRetry:
    async def test_succeeds_on_first_try(self):
        inner = _make_adapter()
        inner.chat.return_value = LLMResponse(content="ok", model="m", usage={})
        resilient = ResilientAdapter(inner, breaker=_CircuitBreaker())
        result = await resilient.chat([LLMMessage(role="user", content="hi")])
        assert result.content == "ok"
        assert inner.chat.call_count == 1

    async def test_retries_on_failure(self):
        inner = _make_adapter()
        inner.chat.side_effect = [
            RuntimeError("fail1"),
            LLMResponse(content="ok", model="m", usage={}),
        ]
        resilient = ResilientAdapter(inner, max_retries=3, breaker=_CircuitBreaker())
        result = await resilient.chat([LLMMessage(role="user", content="hi")])
        assert result.content == "ok"
        assert inner.chat.call_count == 2

    async def test_exhausts_retries(self):
        inner = _make_adapter()
        inner.chat.side_effect = RuntimeError("always fails")
        resilient = ResilientAdapter(inner, max_retries=2, breaker=_CircuitBreaker())
        with pytest.raises(RuntimeError, match="always fails"):
            await resilient.chat([LLMMessage(role="user", content="hi")])
        assert inner.chat.call_count == 2

    async def test_timeout(self):
        inner = _make_adapter()

        async def slow_chat(*args, **kwargs):
            await asyncio.sleep(10)

        inner.chat = slow_chat
        resilient = ResilientAdapter(
            inner, max_retries=1, timeout_seconds=0.1, breaker=_CircuitBreaker()
        )
        with pytest.raises(asyncio.TimeoutError):
            await resilient.chat([LLMMessage(role="user", content="hi")])


class TestCircuitBreaker:
    async def test_opens_after_threshold(self):
        breaker = _CircuitBreaker(threshold=2, recovery_seconds=60)
        inner = _make_adapter()
        inner.chat.side_effect = RuntimeError("fail")
        resilient = ResilientAdapter(inner, max_retries=1, breaker=breaker)

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await resilient.chat([LLMMessage(role="user", content="hi")])

        with pytest.raises(CircuitOpenError):
            await resilient.chat([LLMMessage(role="user", content="hi")])

    async def test_recovers_after_timeout(self):
        breaker = _CircuitBreaker(threshold=1, recovery_seconds=0)
        inner = _make_adapter()
        inner.chat.side_effect = RuntimeError("fail")
        resilient = ResilientAdapter(inner, max_retries=1, breaker=breaker)

        with pytest.raises(RuntimeError):
            await resilient.chat([LLMMessage(role="user", content="hi")])

        inner.chat.side_effect = None
        inner.chat.return_value = LLMResponse(content="recovered", model="m", usage={})
        result = await resilient.chat([LLMMessage(role="user", content="hi")])
        assert result.content == "recovered"
