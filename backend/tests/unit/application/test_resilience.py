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

    async def test_no_retry_on_client_error(self):
        """4xx 客户端错误(403)不重试, 立即抛出 (scan 409 根因修复)."""
        inner = _make_adapter()
        # 模拟 SDK 透传的 403 Forbidden (APIStatusError 带 status_code)
        exc = PermissionError("consumer has not enabled this model")
        exc.status_code = 403  # type: ignore[attr-defined]
        inner.chat.side_effect = exc
        resilient = ResilientAdapter(inner, max_retries=3, breaker=_CircuitBreaker())
        with pytest.raises(PermissionError, match="consumer has not enabled"):
            await resilient.chat([LLMMessage(role="user", content="hi")])
        # 不重试 — 仅调用 1 次
        assert inner.chat.call_count == 1

    async def test_no_retry_on_400_but_retry_on_429(self):
        """400 不重试, 429 限流仍重试."""
        inner = _make_adapter()
        exc400 = ValueError("bad request")
        exc400.status_code = 400  # type: ignore[attr-defined]
        inner.chat.side_effect = exc400
        resilient = ResilientAdapter(inner, max_retries=3, breaker=_CircuitBreaker())
        with pytest.raises(ValueError):
            await resilient.chat([LLMMessage(role="user", content="hi")])
        assert inner.chat.call_count == 1  # 400 不重试

        # 429 限流 → 重试到耗尽
        inner2 = _make_adapter()
        exc429 = RuntimeError("rate limited")
        exc429.status_code = 429  # type: ignore[attr-defined]
        inner2.chat.side_effect = exc429
        resilient2 = ResilientAdapter(inner2, max_retries=2, breaker=_CircuitBreaker())
        with pytest.raises(RuntimeError):
            await resilient2.chat([LLMMessage(role="user", content="hi")])
        assert inner2.chat.call_count == 2  # 429 重试


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
