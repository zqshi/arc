"""Deployment 路由集成测试 (v5.5.0)。

覆盖 rollback / list / latest 三个端点的 happy path + 权限 + 404。
不依赖 S3: 直接在 DB 插入 DeploymentModel 记录后调 endpoint。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import insert

from arc.infrastructure.models.deployment import DeploymentModel


async def _make_project(client: AsyncClient, name: str = "Deploy Test") -> tuple[str, str]:
    """创建项目 + version，返回 (project_id, version_id)。"""
    resp = await client.post("/api/projects", json={"name": name})
    assert resp.status_code in (200, 201)
    project_id = resp.json()["id"]

    # 项目创建不自动建 version，显式创建一个
    resp = await client.post(
        f"/api/projects/{project_id}/versions",
        json={"name": "v1.0", "goal": "test", "version_type": "minor"},
    )
    assert resp.status_code == 201
    version_id = resp.json()["id"]
    return project_id, version_id


async def _insert_deployment(
    db_session, project_id: str, version_id: str, *, status: str = "deployed"
) -> str:
    """直接插入一条 DeploymentModel 记录，返回 deployment_id。"""
    deploy_id = uuid.uuid4()
    await db_session.execute(
        insert(DeploymentModel).values(
            id=deploy_id,
            project_id=uuid.UUID(project_id),
            version_id=uuid.UUID(version_id),
            todo_id=None,
            status=status,
            deploy_type="static_site",
            build_command="npm run build",
            artifact_path="dist",
            deploy_url="https://cdn.example.com/deployments/test/index.html",
            storage_prefix="deployments/test",
            files_uploaded=12,
            deployed_at=datetime.now(UTC) if status == "deployed" else None,
        )
    )
    await db_session.commit()
    return str(deploy_id)


class TestDeploymentList:
    async def test_list_returns_deployments(self, client: AsyncClient, db_session):
        project_id, version_id = await _make_project(client)
        await _insert_deployment(db_session, project_id, version_id)

        resp = await client.get(f"/api/projects/{project_id}/deployments")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1
        assert data["items"][0]["status"] == "deployed"
        assert "deploy_url" in data["items"][0]

    async def test_list_supports_pagination(self, client: AsyncClient, db_session):
        project_id, version_id = await _make_project(client, "Deploy Pagination")
        for _ in range(3):
            await _insert_deployment(db_session, project_id, version_id)

        resp = await client.get(
            f"/api/projects/{project_id}/deployments", params={"skip": 0, "limit": 2}
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) <= 2

    async def test_list_nonexistent_project_returns_404(self, client: AsyncClient):
        resp = await client.get(f"/api/projects/{uuid.uuid4()}/deployments")
        assert resp.status_code == 404


class TestDeploymentRollback:
    async def test_rollback_marks_rolled_back(self, client: AsyncClient, db_session):
        project_id, version_id = await _make_project(client, "Rollback Test")
        deploy_id = await _insert_deployment(
            db_session, project_id, version_id, status="deployed"
        )

        resp = await client.post(
            f"/api/projects/{project_id}/deployments/{deploy_id}/rollback"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "rolled_back"
        assert data["id"] == deploy_id
        # 文件未被删除: deploy_url 仍保留
        assert data["deploy_url"] is not None

    async def test_rollback_nonexistent_deployment_returns_404(
        self, client: AsyncClient, db_session
    ):
        project_id, _ = await _make_project(client, "Rollback 404")
        fake_deploy_id = uuid.uuid4()

        resp = await client.post(
            f"/api/projects/{project_id}/deployments/{fake_deploy_id}/rollback"
        )
        assert resp.status_code == 404

    async def test_rollback_nonexistent_project_returns_404(self, client: AsyncClient):
        fake_project = uuid.uuid4()
        fake_deploy = uuid.uuid4()
        resp = await client.post(
            f"/api/projects/{fake_project}/deployments/{fake_deploy}/rollback"
        )
        assert resp.status_code == 404


class TestLatestDeployment:
    async def test_latest_returns_most_recent(self, client: AsyncClient, db_session):
        project_id, version_id = await _make_project(client, "Latest Deploy")
        await _insert_deployment(db_session, project_id, version_id, status="deployed")

        resp = await client.get(
            f"/api/projects/{project_id}/versions/{version_id}/deployment/latest"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deployed"

    async def test_latest_no_deployment_returns_404(
        self, client: AsyncClient, db_session
    ):
        project_id, version_id = await _make_project(client, "Latest 404")

        resp = await client.get(
            f"/api/projects/{project_id}/versions/{version_id}/deployment/latest"
        )
        assert resp.status_code == 404
