"""A3 metrics 集成测试 — /metrics 端点 + HTTP 指标 + 路由归一化 + Agent 任务埋点。

prometheus_client 全局注册表跨测试累积, 故断言用"递增/存在"非"等于"。
"""

from __future__ import annotations

from httpx import AsyncClient


def _count_sample(text: str, metric: str, **labels: str) -> float:
    """从 exposition 文本中取某 metric+label 组合的样本值 (取最后一行匹配, 多 worker 不涉及)。"""
    target_labels = "".join(f'{k}="{v}",' for k, v in labels.items()).rstrip(",")
    for line in reversed(text.splitlines()):
        if not line.startswith(metric):
            continue
        if target_labels and target_labels not in line:
            continue
        parts = line.split()
        try:
            return float(parts[-1])
        except (ValueError, IndexError):
            continue
    return 0.0


class TestMetricsEndpoint:
    async def test_metrics_exposition(self, client: AsyncClient):
        """GET /metrics 返回 200 + 标准 content-type + 含 arc_ 指标名。"""
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        body = resp.text
        assert "arc_http_requests_total" in body
        assert "arc_http_request_duration_seconds" in body

    async def test_metrics_no_auth(self, client: AsyncClient):
        """/metrics 不挂 auth — 未带 token 也能访问 (Prometheus scraper 无登录态)。"""
        resp = await client.get("/metrics")
        assert resp.status_code == 200


class TestHttpMetrics:
    async def test_request_count_increments(self, client: AsyncClient):
        """发请求后 arc_http_requests_total 对应 label 递增。"""
        before = _count_sample(
            (await client.get("/metrics")).text,
            "arc_http_requests_total", method="GET", path="/health", status="200",
        )
        await client.get("/health")
        after = _count_sample(
            (await client.get("/metrics")).text,
            "arc_http_requests_total", method="GET", path="/health", status="200",
        )
        assert after > before

    async def test_route_template_normalization(self, client: AsyncClient):
        """具体资源 id 不入 path label — /api/todos/{uuid} 归一化为路由模板。

        注: Starlette path_format 不含 include_router prefix, 故 todos 路由模板是
        /{todo_id} (prefix /api/todos 在 router 层), 归一化目的 = uuid 不入 label, 达成。
        """
        await client.get("/api/todos/00000000-0000-0000-0000-000000000000")
        metrics = (await client.get("/metrics")).text
        # uuid 被归一化为模板 {todo_id}, 不应出现具体 uuid 作为 path label
        assert "path=\"/api/todos/00000000-0000-0000-0000-000000000000\"" not in metrics
        assert "{todo_id}" in metrics

    async def test_error_status_counted(self, client: AsyncClient):
        """404 异常路径也被计数 (最外层中间件覆盖)。"""
        await client.get("/api/no-such-path-zzz-metrics-test")
        metrics = (await client.get("/metrics")).text
        assert "status=\"404\"" in metrics


class TestAgentTaskMetrics:
    """Agent autopilot 任务耗时埋点 — outcome=complete/paused/timeout/error。

    端到端 agent 执行 blocked 于 LLM 凭证, 这里验证指标定义存在 + AGENT_TASK_DURATION
    可被 observe (不抛异常), 指标出现在 /metrics。真实耗时分布待端到端验证。
    """

    async def test_agent_metric_exposed(self, client: AsyncClient):
        """/metrics 暴露 arc_agent_task_duration_seconds 指标 (含 _bucket/_sum/_count)。"""
        # 直接 observe 一次确保指标有数据点
        from arc.application.execution.metrics import AGENT_TASK_DURATION

        AGENT_TASK_DURATION.labels(outcome="paused").observe(0.001)

        metrics = (await client.get("/metrics")).text
        assert "arc_agent_task_duration_seconds" in metrics
        assert "outcome=\"paused\"" in metrics


class TestBaasMetrics:
    """BaaS provision 运维指标埋点 (续9) — result=success|skip|fail + reason。

    真实 provision 链路 blocked 于 LLM 凭证 (走对话产出 tech_architecture 才触发 hook),
    这里验证指标定义存在 + BAAS_PROVISION_TOTAL 可被 inc + 出现在 /metrics。
    真实失败率/skip 分布待生产端到端累积。
    """

    async def test_baas_metrics_exposed(self, client: AsyncClient):
        """/metrics 暴露 arc_baas_provision_total + arc_baas_provision_duration_seconds (续9)。"""
        from arc.application.baas.metrics import BAAS_PROVISION_TOTAL

        # inc 一次确保 Counter 有数据点 (skip_no_aggregates 是高频正常路径)
        BAAS_PROVISION_TOTAL.labels(result="skip", reason="skip_no_aggregates").inc()

        metrics = (await client.get("/metrics")).text
        assert "arc_baas_provision_total" in metrics
        assert "arc_baas_provision_duration_seconds" in metrics
        assert 'result="skip"' in metrics
        assert 'reason="skip_no_aggregates"' in metrics
