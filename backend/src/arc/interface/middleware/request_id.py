"""Request ID middleware — assigns a unique trace ID to every request."""

from __future__ import annotations

import contextvars
import logging
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

_HEADER = "X-Request-ID"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")
        return True


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get(_HEADER) or uuid.uuid4().hex[:16]
        request_id_var.set(rid)
        request.state.request_id = rid

        response: Response = await call_next(request)
        response.headers[_HEADER] = rid
        return response
