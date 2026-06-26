"""项目环节能力配置 API 集成测试 (v6.8.0 W3).

真实链路: route → require_project_role(ADMIN) → ProjectWorkspaceService
→ CapabilityService 校验 (存在/active) → Project.update_phase_capabilities → 持久化。
owner 自动满足 admin (require_project_role 对 owner 直接放行)。
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


class TestPhaseCapabilitiesCRUD:
    async def test_update_and_read_back(self, client, cleanup):
        """配 skill 能力到 development 环节 → GET 项目回读校验。"""
        create = await client.post("/api/projects", json={"name": "PC CRUD"})
        pid = create.json()["id"]
        cap = await client.post(
            "/api/capabilities",
            json={"name": "ui-skill", "type": "skill", "config": {"directory": "/x"}},
        )
        cap_id = cap.json()["id"]

        resp = await client.put(
            f"/api/projects/{pid}/pipeline/phase-capabilities",
            json={"phase": "development", "capability_ids": [cap_id]},
        )
        assert resp.status_code == 200
        assert resp.json()["phase_capabilities"]["development"] == [cap_id]

        proj = await client.get(f"/api/projects/{pid}")
        assert proj.json()["pipeline_config"]["phase_capabilities"]["development"] == [cap_id]

    async def test_clear_phase_capabilities(self, client, cleanup):
        """空 capability_ids 清空该环节配置。"""
        create = await client.post("/api/projects", json={"name": "PC Clear"})
        pid = create.json()["id"]
        cap = await client.post("/api/capabilities", json={"name": "s2", "type": "skill"})
        await client.put(
            f"/api/projects/{pid}/pipeline/phase-capabilities",
            json={"phase": "testing", "capability_ids": [cap.json()["id"]]},
        )

        resp = await client.put(
            f"/api/projects/{pid}/pipeline/phase-capabilities",
            json={"phase": "testing", "capability_ids": []},
        )
        assert resp.status_code == 200
        assert resp.json()["phase_capabilities"]["testing"] == []

    async def test_invalid_phase_returns_400(self, client, cleanup):
        create = await client.post("/api/projects", json={"name": "PC Bad Phase"})
        pid = create.json()["id"]
        resp = await client.put(
            f"/api/projects/{pid}/pipeline/phase-capabilities",
            json={"phase": "not_a_phase", "capability_ids": []},
        )
        assert resp.status_code == 400

    async def test_capability_not_found_returns_404(self, client, cleanup):
        create = await client.post("/api/projects", json={"name": "PC Ghost"})
        pid = create.json()["id"]
        resp = await client.put(
            f"/api/projects/{pid}/pipeline/phase-capabilities",
            json={"phase": "development", "capability_ids": [str(uuid.uuid4())]},
        )
        assert resp.status_code == 404

    async def test_disabled_capability_returns_409(self, client, cleanup):
        create = await client.post("/api/projects", json={"name": "PC Disabled"})
        pid = create.json()["id"]
        cap = await client.post(
            "/api/capabilities",
            json={"name": "dis", "type": "skill", "status": "disabled"},
        )
        resp = await client.put(
            f"/api/projects/{pid}/pipeline/phase-capabilities",
            json={"phase": "development", "capability_ids": [cap.json()["id"]]},
        )
        assert resp.status_code == 409
