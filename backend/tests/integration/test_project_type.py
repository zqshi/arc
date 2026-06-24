"""项目类型 (project_type) 集成测试 (v5.9.0)。

验证 project_type 贯穿: 创建 → DB 持久化 → 响应返回, 以及 schema 约束。
端到端覆盖 T2(domain) + T6(schema/route/service) + T7(ORM/migration) 三层。
"""
from __future__ import annotations

from httpx import AsyncClient


class TestProjectType:
    async def test_create_defaults_to_static_site(self, client: AsyncClient):
        resp = await client.post("/api/projects", json={"name": "PT Default"})
        assert resp.status_code in (200, 201)
        assert resp.json()["project_type"] == "static_site"

    async def test_create_explicit_static_site(self, client: AsyncClient):
        resp = await client.post(
            "/api/projects",
            json={"name": "PT Explicit", "project_type": "static_site"},
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["project_type"] == "static_site"

    async def test_project_type_persists_across_requests(self, client: AsyncClient):
        """GET 重新查询验证 DB 持久化, 排除内存默认值假象。"""
        create = await client.post("/api/projects", json={"name": "PT Persist"})
        pid = create.json()["id"]

        resp = await client.get(f"/api/projects/{pid}")
        assert resp.status_code == 200
        assert resp.json()["project_type"] == "static_site"

    async def test_create_accepts_binary_app(self, client: AsyncClient):
        """v6.0.0 binary_app 已激活, schema Literal 允许 → 201。"""
        resp = await client.post(
            "/api/projects",
            json={"name": "PT Binary", "project_type": "binary_app"},
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["project_type"] == "binary_app"

    async def test_create_rejects_unsupported_type(self, client: AsyncClient):
        """未激活类型(library) schema Literal 约束 → 422。"""
        resp = await client.post(
            "/api/projects",
            json={"name": "PT Bad", "project_type": "library"},
        )
        assert resp.status_code == 422
