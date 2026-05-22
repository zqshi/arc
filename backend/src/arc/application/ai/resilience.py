"""Resilient LLM adapter wrapper with retry, timeout, and circuit breaker."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import AsyncIterator

from arc.application.ai.llm_adapter import LLMAdapter, LLMMessage, LLMResponse, StreamResult

logger = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 2
_DEFAULT_TIMEOUT_SECONDS = 300
_CB_FAILURE_THRESHOLD = 5
_CB_RECOVERY_SECONDS = 30


class CircuitOpenError(Exception):
    pass


class _CircuitBreaker:
    __slots__ = ("_threshold", "_recovery", "_failures", "_last_failure", "_state")

    def __init__(
        self,
        threshold: int = _CB_FAILURE_THRESHOLD,
        recovery_seconds: float = _CB_RECOVERY_SECONDS,
    ):
        self._threshold = threshold
        self._recovery = recovery_seconds
        self._failures = 0
        self._last_failure = 0.0
        self._state = "closed"

    def before_call(self) -> None:
        if self._state == "open":
            if time.monotonic() - self._last_failure >= self._recovery:
                self._state = "half-open"
                logger.info("Circuit breaker half-open, allowing probe request")
            else:
                raise CircuitOpenError(
                    f"LLM circuit breaker open — {self._failures} consecutive failures. "
                    f"Retry in {int(self._recovery - (time.monotonic() - self._last_failure))}s"
                )

    def on_success(self) -> None:
        if self._state == "half-open":
            logger.info("Circuit breaker closed after successful probe")
        self._failures = 0
        self._state = "closed"

    def on_failure(self) -> None:
        self._failures += 1
        self._last_failure = time.monotonic()
        if self._failures >= self._threshold:
            self._state = "open"
            logger.warning("Circuit breaker opened after %d consecutive failures", self._failures)


_chat_breaker = _CircuitBreaker()
_embed_breaker = _CircuitBreaker()


class ResilientAdapter(LLMAdapter):
    """Wraps any LLMAdapter with retry, timeout, and circuit breaker."""

    def __init__(
        self,
        inner: LLMAdapter,
        *,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        breaker: _CircuitBreaker | None = None,
    ):
        self._inner = inner
        self._max_retries = max_retries
        self._timeout = timeout_seconds
        self._chat_breaker = breaker or _chat_breaker
        self._embed_breaker = _embed_breaker if breaker is None else breaker

    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        return await self._retry(
            lambda: asyncio.wait_for(
                self._inner.chat(messages, temperature=temperature, max_tokens=max_tokens),
                timeout=self._timeout,
            ),
            breaker=self._chat_breaker,
        )

    async def chat_stream(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream_idle_timeout: float = 60.0,
    ) -> AsyncIterator[str]:
        self._chat_breaker.before_call()
        started = False
        try:
            stream = self._inner.chat_stream(
                messages, temperature=temperature, max_tokens=max_tokens
            )
            ait = stream.__aiter__()
            while True:
                try:
                    chunk = await asyncio.wait_for(ait.__anext__(), timeout=stream_idle_timeout)
                except StopAsyncIteration:
                    break
                except asyncio.TimeoutError:
                    raise asyncio.TimeoutError(
                        f"LLM stream idle for {stream_idle_timeout}s — connection likely stalled"
                    )
                if not started:
                    self._chat_breaker.on_success()
                    started = True
                yield chunk
            if not started:
                self._chat_breaker.on_success()
        except (CircuitOpenError, asyncio.CancelledError):
            raise
        except Exception:
            self._chat_breaker.on_failure()
            raise

    async def chat_stream_with_result(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream_idle_timeout: float = 60.0,
    ) -> tuple[AsyncIterator[str], StreamResult]:
        self._chat_breaker.before_call()
        inner_iter, result = await self._inner.chat_stream_with_result(
            messages, temperature=temperature, max_tokens=max_tokens
        )

        async def _wrap():
            started = False
            try:
                ait = inner_iter.__aiter__()
                while True:
                    try:
                        chunk = await asyncio.wait_for(ait.__anext__(), timeout=stream_idle_timeout)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        result.finish_reason = "error"
                        raise asyncio.TimeoutError(
                            f"LLM stream idle {stream_idle_timeout}s — stalled"
                        )
                    if not started:
                        self._chat_breaker.on_success()
                        started = True
                    yield chunk
                if not started:
                    self._chat_breaker.on_success()
            except (CircuitOpenError, asyncio.CancelledError):
                raise
            except asyncio.TimeoutError:
                raise
            except Exception:
                self._chat_breaker.on_failure()
                result.finish_reason = "error"
                raise

        return _wrap(), result

    async def embed(self, text: str) -> list[float]:
        return await self._retry(
            lambda: asyncio.wait_for(self._inner.embed(text), timeout=self._timeout),
            breaker=self._embed_breaker,
        )

    async def close(self) -> None:
        await self._inner.close()

    async def _retry(self, fn, *, breaker: _CircuitBreaker):
        last_exc = None
        for attempt in range(self._max_retries):
            breaker.before_call()
            try:
                result = await fn()
                breaker.on_success()
                return result
            except CircuitOpenError:
                raise
            except asyncio.TimeoutError:
                breaker.on_failure()
                last_exc = asyncio.TimeoutError(f"LLM request timed out after {self._timeout}s")
                logger.warning("LLM timeout (attempt %d/%d)", attempt + 1, self._max_retries)
            except Exception as exc:
                breaker.on_failure()
                last_exc = exc
                logger.warning("LLM error (attempt %d/%d): %s", attempt + 1, self._max_retries, exc)

            if attempt < self._max_retries - 1:
                delay = min(2**attempt, 8)
                await asyncio.sleep(delay)

        raise last_exc


def create_resilient_adapter(
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> ResilientAdapter:
    """Factory: create a resilient adapter wrapping the configured LLM provider."""
    from arc.application.ai.llm_adapter import create_llm_adapter

    inner = create_llm_adapter()
    return ResilientAdapter(inner, max_retries=max_retries, timeout_seconds=timeout_seconds)
