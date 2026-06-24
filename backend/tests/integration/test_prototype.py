"""原型预览相关路由的集成测试。"""

from __future__ import annotations

import uuid

from httpx import ASGITransport, AsyncClient


class TestPrototypeStatus:
    async def test_status_returns_200(self, client: AsyncClient, db_session):
        """创建项目后查询 prototype-status 应返回 200。"""
        # 先创建一个项目
        resp = await client.post("/api/projects", json={
            "name": "Prototype Status Test",
            "description": "测试原型状态",
        })
        assert resp.status_code in (200, 201)
        project_id = resp.json()["id"]

        # 查询 prototype-status
        resp = await client.get(f"/api/projects/{project_id}/prototype-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "has_prototype" in data
        assert "total_pages" in data
        assert data["has_prototype"] is False
        assert data["total_pages"] == 0

    async def test_status_nonexistent_project_returns_404(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/projects/{fake_id}/prototype-status")
        assert resp.status_code == 404


class TestPrototypeBundle:
    async def test_bundle_empty_project(self, client: AsyncClient, db_session):
        """项目无原型时 bundle 应返回空列表。"""
        resp = await client.post("/api/projects", json={
            "name": "Bundle Empty Test",
        })
        assert resp.status_code in (200, 201)
        project_id = resp.json()["id"]

        resp = await client.get(f"/api/projects/{project_id}/prototype-bundle")
        assert resp.status_code == 200
        data = resp.json()
        # schema 已从 HTML 片段时代的 pages/new_pages 升级为前端工程语义的 routes
        assert data["routes"] == []
        assert data["total_pages"] == 0

    async def test_bundle_nonexistent_project_returns_404(self, client: AsyncClient):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/projects/{fake_id}/prototype-bundle")
        assert resp.status_code == 404


class TestPrototypePreview:
    async def test_preview_without_token_returns_401(self, db_session):
        """prototype-preview 无 token 时应返回 401。"""
        from arc.interface.deps import get_db
        from arc.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as raw_client:
            fake_id = str(uuid.uuid4())
            resp = await raw_client.get(
                f"/api/projects/{fake_id}/prototype-preview"
            )
            assert resp.status_code == 401

        app.dependency_overrides.clear()

    async def test_preview_with_invalid_token_returns_401(self, db_session):
        """prototype-preview 错误 token 应返回 401。"""
        from arc.interface.deps import get_db
        from arc.main import app

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as raw_client:
            fake_id = str(uuid.uuid4())
            resp = await raw_client.get(
                f"/api/projects/{fake_id}/prototype-preview?token=invalid_token_xxx"
            )
            assert resp.status_code == 401

        app.dependency_overrides.clear()
