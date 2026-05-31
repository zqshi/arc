"""IP-based sliding window rate limiter (in-memory).

For multi-instance deployments, replace the in-memory store with Redis.
"""

from __future__ import annotations

import time
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
    def __init__(self, app, default_limit: int = _DEFAULT_LIMIT, window: int = _DEFAULT_WINDOW):
        super().__init__(app)
        self._default_limit = default_limit
        self._window = window
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._last_gc = time.monotonic()

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

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in ("/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # SSE streams are long-lived connections, not rapid-fire requests
        if request.url.path.endswith("/stream"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{request.url.path}"
        now = time.monotonic()
        limit = self._get_limit(request.url.path)

        self._maybe_gc(now)

        hits = self._hits[key]
        hits[:] = [t for t in hits if now - t < self._window]

        if len(hits) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试", "error_code": "RATE_LIMITED"},
            )

        hits.append(now)
        return await call_next(request)
