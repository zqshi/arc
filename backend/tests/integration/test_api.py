from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient

from arc.interface.middleware.request_id import RequestIdFilter


class TestHealthEndpoint:
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"

    async def test_health_degraded_when_db_error(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ):
        """DB execute 抛异常时 /health 返回 degraded(200), 非 500。

        覆盖 /health 异常分支: 全局 factory 创建的 session execute 失败时, 端点应
        捕获并降级, 而非冒泡 500(健康检查端点必须总返回 200 + status)。
        """
        from arc.infrastructure import database as db_module

        class _BadSession:
            async def execute(self, *_args, **_kwargs):
                raise RuntimeError("simulated db failure")

        @asynccontextmanager
        async def _broken_factory():
            yield _BadSession()

        monkeypatch.setattr(db_module, "async_session_factory", _broken_factory)

        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert "RuntimeError" in data["database"]


class TestAccessLog:
    """A1: RequestIdMiddleware 记录请求级 access log (method/path/status/duration_ms + request_id)。"""

    async def test_access_log_success(self, client: AsyncClient, caplog: pytest.LogCaptureFixture):
        # caplog 的 LogCaptureHandler 绕过 root handler 上的 RequestIdFilter, 这里复现生产 filter 链,
        # 使捕获的 record 同样被注入 request_id (证明 access log 经 root handler 输出时必带 rid)。
        caplog.handler.addFilter(RequestIdFilter())
        with caplog.at_level(logging.INFO, logger="arc.access"):
            resp = await client.get("/health")
        assert resp.status_code == 200
        access = [r for r in caplog.records if r.name == "arc.access"]
        assert len(access) == 1
        rec = access[0]
        assert rec.method == "GET"
        assert rec.path == "/health"
        assert rec.status == 200
        assert isinstance(rec.duration_ms, int) and rec.duration_ms >= 0
        assert rec.request_id  # RequestIdFilter 经 request_id_var 注入, 非空

    async def test_access_log_404(self, client: AsyncClient, caplog: pytest.LogCaptureFixture):
        caplog.handler.addFilter(RequestIdFilter())
        with caplog.at_level(logging.INFO, logger="arc.access"):
            resp = await client.get("/api/no-such-path-zzz")
        assert resp.status_code == 404
        access = [r for r in caplog.records if r.name == "arc.access"]
        assert len(access) == 1
        assert access[0].status == 404
        assert access[0].path == "/api/no-such-path-zzz"
        assert access[0].request_id  # 异常路径同样有 request_id


class TestReadyEndpoint:
    """A2: /ready readiness 探针 (DB 恒探 + Redis/S3 配了才探, 失败 503 摘流量)。"""

    async def test_ready_db_only(self, client: AsyncClient):
        """测试环境无 redis_url/storage_endpoint → redis/storage skipped, status=ready 200。"""
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"
        assert data["redis"] == "skipped"
        assert data["storage"] == "skipped"

    async def test_ready_503_when_db_down(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ):
        """DB 不可达 → status=not_ready + 503 (k8s readinessProbe 摘流量)。"""
        from arc.infrastructure import database as db_module

        class _BadSession:
            async def execute(self, *_args, **_kwargs):
                raise RuntimeError("simulated db failure")

        @asynccontextmanager
        async def _broken_factory():
            yield _BadSession()

        monkeypatch.setattr(db_module, "async_session_factory", _broken_factory)

        resp = await client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"
        assert "RuntimeError" in data["database"]


class TestTodoCRUD:
    async def test_create_and_list(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={
            "title": "集成测试任务",
            "description": "测试创建待办",
            "tags": [{"label": "测试", "color": "#EF4444"}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "集成测试任务"
        assert data["status"] == "pending"
        todo_id = data["id"]

        resp = await client.get("/api/todos")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(t["id"] == todo_id for t in items)

    async def test_get_single(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={"title": "单条查询"})
        todo_id = resp.json()["id"]

        resp = await client.get(f"/api/todos/{todo_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "单条查询"

    async def test_update(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={"title": "待更新"})
        todo_id = resp.json()["id"]

        resp = await client.put(f"/api/todos/{todo_id}", json={
            "title": "已更新",
            "description": "更新后的描述",
        })
        assert resp.status_code == 200
        assert resp.json()["title"] == "已更新"
        assert resp.json()["description"] == "更新后的描述"

    async def test_delete(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={"title": "待删除"})
        todo_id = resp.json()["id"]

        resp = await client.delete(f"/api/todos/{todo_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/todos/{todo_id}")
        assert resp.status_code == 404

    async def test_not_found(self, client: AsyncClient):
        resp = await client.get("/api/todos/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


class TestTodoLifecycle:
    async def test_filter_by_status(self, client: AsyncClient):
        resp = await client.post("/api/todos", json={"title": "筛选测试"})
        resp = await client.get("/api/todos?status=pending")
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["status"] == "pending"


class TestExperienceCRUD:
    async def test_create_and_list(self, client: AsyncClient):
        resp = await client.post("/api/experiences", json={
            "title": "测试经验",
            "scope": "project",
            "problem": "遇到问题",
            "solution": "解决方案",
            "decisions": ["决策1"],
            "pitfalls": ["坑1"],
            "tags": [{"label": "测试", "color": "#34D399"}],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "测试经验"
        assert data["scope"] == "project"

        resp = await client.get("/api/experiences")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_single(self, client: AsyncClient):
        resp = await client.post("/api/experiences", json={
            "title": "查询经验",
            "problem": "p",
            "solution": "s",
        })
        exp_id = resp.json()["id"]

        resp = await client.get(f"/api/experiences/{exp_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "查询经验"
