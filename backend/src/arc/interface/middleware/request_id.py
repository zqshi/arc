"""Request ID middleware — assigns a unique trace ID to every request."""

from __future__ import annotations

import contextvars
import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

_HEADER = "X-Request-ID"

# 独立 access logger — 继承 root handler (StructuredFormatter + RequestIdFilter),
# request_id 由 RequestIdFilter 经 request_id_var 自动注入, 无需手动传。
_access_logger = logging.getLogger("arc.access")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get(_HEADER) or uuid.uuid4().hex[:16]
        request_id_var.set(rid)
        request.state.request_id = rid

        start = time.perf_counter()
        status = 500  # 异常冒泡前默认 500, 保证异常请求也有 access log
        try:
            response: Response = await call_next(request)
            status = response.status_code
            response.headers[_HEADER] = rid
            return response
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            _access_logger.info(
                "%s %s -> %d (%dms)",
                request.method,
                request.url.path,
                status,
                duration_ms,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": duration_ms,
                },
            )
