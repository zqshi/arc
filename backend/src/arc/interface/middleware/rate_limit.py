"""IP-based sliding window rate limiter.

内存滑动窗口 (单 worker/dev) 或 Redis sorted set (多副本生产, redis_url 非空)。
B5 投产门禁: 多副本下进程内存态限流被副本数倍绕过, redis_url 配置后切 Redis 共享计数。
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_DEFAULT_LIMIT = 120
_DEFAULT_WINDOW = 60
_LLM_PATHS = {"/ws/chat", "/api/todos/", "/api/conversations/"}
_LLM_LIMIT = 20
_MAX_KEYS = 10_000
_GC_INTERVAL = 300


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        default_limit: int = _DEFAULT_LIMIT,
        window: int = _DEFAULT_WINDOW,
        redis_url: str = "",
    ):
        super().__init__(app)
        self._default_limit = default_limit
        self._window = window
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._last_gc = time.time()
        self._redis = None
        if redis_url:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(redis_url, decode_responses=True)

    def _get_limit(self, path: str) -> int:
        for prefix in _LLM_PATHS:
            if prefix in path and ("pipeline" in path or "chat" in path or "agent" in path):
                return _LLM_LIMIT
        return self._default_limit

    def _maybe_gc(self, now: float) -> None:
        if now - self._last_gc < _GC_INTERVAL or len(self._hits) < _MAX_KEYS:
            return
        expired = [k for k, v in self._hits.items() if not v or now - v[-1] >= self._window]
        for k in expired:
            del self._hits[k]
        self._last_gc = now

    def _check_memory(self, key: str, now: float, limit: int) -> bool:
        """内存滑动窗口. 返回 True=允许, False=限流。"""
        hits = self._hits[key]
        hits[:] = [t for t in hits if now - t < self._window]
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True

    async def _check_redis(self, key: str, now: float, limit: int) -> bool:
        """Redis sorted set 滑动窗口 (多副本共享计数). 返回 True=允许, False=限流。"""
        r = self._redis
        await r.zremrangebyscore(key, 0, now - self._window)
        count = await r.zcard(key)
        if count >= limit:
            return False
        await r.zadd(key, {f"{now}:{uuid.uuid4().hex[:8]}": now})
        await r.expire(key, self._window)
        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # SSE streams are long-lived connections, not rapid-fire requests
        if request.url.path.endswith("/stream"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"
        now = time.time()
        limit = self._get_limit(request.url.path)

        if self._redis:
            allowed = await self._check_redis(key, now, limit)
        else:
            self._maybe_gc(now)
            allowed = self._check_memory(key, now, limit)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试", "error_code": "RATE_LIMITED"},
            )
        return await call_next(request)
