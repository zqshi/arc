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

    async def test_create_binary_app_web_target_injects_sandbox(self, client: AsyncClient):
        """v6.12: binary_app + build_target=web → conversation_config.sandbox 注入 target。"""
        resp = await client.post(
            "/api/projects",
            json={"name": "PT Web", "project_type": "binary_app", "build_target": "web"},
        )
        assert resp.status_code in (200, 201)
        sandbox = resp.json()["conversation_config"]["sandbox"]
        assert sandbox["mode"] == "docker"
        assert sandbox["target"] == "web"

    async def test_create_binary_app_capacitor_apk_injects_memory(self, client: AsyncClient):
        """v6.12: capacitor_apk 注入 sandbox + memory_limit_mb=4096 (android 构建重)。"""
        resp = await client.post(
            "/api/projects",
            json={
                "name": "PT Apk",
                "project_type": "binary_app",
                "build_target": "capacitor_apk",
            },
        )
        assert resp.status_code in (200, 201)
        sandbox = resp.json()["conversation_config"]["sandbox"]
        assert sandbox["target"] == "capacitor_apk"
        assert sandbox["memory_limit_mb"] == 4096

    async def test_create_binary_app_default_target_no_sandbox(self, client: AsyncClient):
        """v6.12: binary_app 不传 build_target → 不注入 sandbox (tauri_linux 走运行时默认推导)。"""
        resp = await client.post(
            "/api/projects",
            json={"name": "PT Default T", "project_type": "binary_app"},
        )
        assert resp.status_code in (200, 201)
        assert "sandbox" not in resp.json()["conversation_config"]

    async def test_create_rejects_invalid_build_target(self, client: AsyncClient):
        """v6.12: 非法 build_target schema Literal 约束 → 422。"""
        resp = await client.post(
            "/api/projects",
            json={"name": "PT BadT", "project_type": "binary_app", "build_target": "ios"},
        )
        assert resp.status_code == 422
