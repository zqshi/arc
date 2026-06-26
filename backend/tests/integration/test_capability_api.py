"""能力管理 API 集成测试 (v6.8.0 W1).

真实 PG + ASGITransport: CRUD + 过滤/分页 + 404/409 + 权限边界 (非 admin 403)。
注: 401 (未认证) 由 get_current_user 全局处理, 非 capability 特有, 此处不重复覆盖。
"""
from __future__ import annotations

import uuid

import pytest


@pytest.fixture
async def cleanup(db_session):
    yield
    from sqlalchemy import text

    await db_session.execute(text("DELETE FROM capabilities"))
    await db_session.commit()


class TestCapabilityAPI:
    @pytest.mark.asyncio
    async def test_create_and_get(self, client, cleanup):
        resp = await client.post(
            "/api/capabilities",
            json={"name": "openhands", "type": "agent", "config": {"adapter": "openhands"}},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "openhands"
        assert body["type"] == "agent"
        assert body["config"]["adapter"] == "openhands"
        cap_id = body["id"]

        get = await client.get(f"/api/capabilities/{cap_id}")
        assert get.status_code == 200
        assert get.json()["name"] == "openhands"

    @pytest.mark.asyncio
    async def test_list_with_filter(self, client, cleanup):
        await client.post("/api/capabilities", json={"name": "a1", "type": "agent"})
        await client.post("/api/capabilities", json={"name": "s1", "type": "skill"})

        resp = await client.get("/api/capabilities?type=agent")
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert names == ["a1"]

        all_resp = await client.get("/api/capabilities")
        assert len(all_resp.json()) == 2

    @pytest.mark.asyncio
    async def test_list_pagination(self, client, cleanup):
        for i in range(5):
            await client.post("/api/capabilities", json={"name": f"c{i}", "type": "agent"})
        resp = await client.get("/api/capabilities?skip=2&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_update(self, client, cleanup):
        create = await client.post("/api/capabilities", json={"name": "old", "type": "agent"})
        cap_id = create.json()["id"]
        resp = await client.patch(
            f"/api/capabilities/{cap_id}", json={"name": "new", "status": "disabled"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "new"
        assert resp.json()["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_delete(self, client, cleanup):
        create = await client.post("/api/capabilities", json={"name": "del", "type": "agent"})
        cap_id = create.json()["id"]
        resp = await client.delete(f"/api/capabilities/{cap_id}")
        assert resp.status_code == 200
        # 删除后再 get → 404
        get = await client.get(f"/api/capabilities/{cap_id}")
        assert get.status_code == 404

    @pytest.mark.asyncio
    async def test_get_not_found(self, client, cleanup):
        resp = await client.get(f"/api/capabilities/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_duplicate_name_conflict(self, client, cleanup):
        await client.post("/api/capabilities", json={"name": "dup", "type": "agent"})
        resp = await client.post("/api/capabilities", json={"name": "dup", "type": "skill"})
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_requires_admin(self, client, cleanup):
        """非 admin 写操作被拒 (403)。"""
        from arc.domain.user.entity import User
        from arc.domain.user.value_objects import UserRole
        from arc.interface.deps import get_current_user
        from arc.main import app

        viewer = User(
            id=uuid.uuid4(), username="viewer", display_name="Viewer", role=UserRole.VIEWER
        )

        async def _viewer():
            return viewer

        app.dependency_overrides[get_current_user] = _viewer
        try:
            resp = await client.post("/api/capabilities", json={"name": "x", "type": "agent"})
            assert resp.status_code == 403
            # 读操作仍允许 (登录即可)
            lst = await client.get("/api/capabilities")
            assert lst.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)
