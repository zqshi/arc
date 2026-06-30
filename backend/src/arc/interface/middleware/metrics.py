"""Prometheus metrics — HTTP 请求指标 + Agent 任务耗时 (v6.19 续7补 A3)。

指标经 prometheus_client 全局注册表聚合, 由 /metrics 端点 (main.py) exposition。
多 worker 各自维护进程内注册表, Prometheus 服务发现聚合 (不自建聚合层)。

设计:
- HTTP 指标按 method+path 归一化路由模板分 label (避免高基数, 具体资源 id 不入 label)。
- 路由模板取 Starlette 的 request.scope["route"].path_format; 未匹配路由回退 raw path。
"""

from __future__ import annotations

import time

from fastapi import Request, Response
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

# --- HTTP 指标定义 (全局注册表, 进程内聚合) ---
# 注: Agent 任务耗时指标 (AGENT_TASK_DURATION) 在 application/execution/metrics.py 定义,
# 因埋点方在 application 层 (DDD: application 禁止 import interface); 全局注册表自动合并。

REQUEST_COUNT = Counter(
    "arc_http_requests_total",
    "HTTP 请求总数 (按 方法/路由/状态码)",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "arc_http_request_duration_seconds",
    "HTTP 请求延迟 (秒)",
    ["method", "path"],
)


def _route_template(request: Request) -> str:
    """归一化路由路径为模板, 避免具体资源 id 打爆 label 基数。

    命中路由 → path_format (如 /api/todos/{todo_id}); 未命中 (404) → raw path。
    """
    route = request.scope.get("route")
    path_format = getattr(route, "path_format", None)
    if path_format:
        return path_format
    return request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """最外层采集中间件 — 记录每个 HTTP 请求的 QPS/状态/延迟 (含异常路径)。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        status = 500  # 异常冒泡前默认 500, 保证异常请求也被计数
        try:
            response: Response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            path = _route_template(request)
            REQUEST_COUNT.labels(request.method, path, status).inc()
            REQUEST_LATENCY.labels(request.method, path).observe(duration)
