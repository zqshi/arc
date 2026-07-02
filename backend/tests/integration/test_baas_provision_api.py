"""BaaS provision 端点 + service 集成测试 (v6.24 P0-1)。

覆盖:
- POST /api/projects/{id}/baas/provision 端点 (skip / 404)
- DomainModelService.provision_baas service (有聚合 -> provision + P0-2 policy 非空)

P0-1: pipeline/refresh/手动端点统一 provision 入口 (之前 pipeline 主路径不触发)。
P0-2: provision 建表带 RLS policy (端到端验证 policy 真建 + user_id DEFAULT auth.uid())。
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from arc.infrastructure.baas.supabase_client import SupabaseClient


async def _cleanup(db_session: AsyncSession, schema_name: str) -> None:
    """asyncpg DROP SCHEMA 持久化 + 删 baas_instances 记录。"""
    client = SupabaseClient()
    try:
        await client.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE', schema=None)
    finally:
        await client.close()
    await db_session.execute(
        text("DELETE FROM baas_instances WHERE schema_name = :name"),
        {"name": schema_name},
    )
    await db_session.commit()


class TestBaasProvisionApi:
    @pytest.mark.asyncio
    async def test_provision_endpoint_skips_when_no_domain_model(self, client):
        """project 无 domain_model -> provisioned=False + reason。"""
        resp = await client.post("/api/projects", json={"name": "Provision NoDM"})
        project_id = resp.json()["id"]

        r = await client.post(f"/api/projects/{project_id}/baas/provision")
        assert r.status_code == 200
        body = r.json()
        assert body["provisioned"] is False
        assert "reason" in body

    @pytest.mark.asyncio
    async def test_provision_endpoint_404_unknown_project(self, client):
        r = await client.post(f"/api/projects/{uuid.uuid4()}/baas/provision")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_provision_baas_builds_schema_with_rls_policies(
        self, client, db_session
    ):
        """有聚合 -> provision + 业务表 + RLS policy 非空 + user_id DEFAULT auth.uid()。

        P0-1 (provision 入口) + P0-2 (policy 非 deny-all) 端到端。
        """
        from arc.application.project.domain_model_service import DomainModelService

        resp = await client.post("/api/projects", json={"name": "Provision E2E"})
        project_id = resp.json()["id"]

        # 设 domain_model (client 建的 project 已持久化; expire_all 强制重读)
        await db_session.execute(
            text(
                "UPDATE projects SET domain_model = CAST(:dm AS jsonb) "
                "WHERE id = CAST(:pid AS uuid)"
            ),
            {
                "dm": json.dumps(
                    {
                        "aggregates": [
                            {"name": "Post", "fields": ["id", "title", "user_id"]},
                            {"name": "Tag", "fields": ["id", "name"]},
                        ],
                        "version": 1,
                    }
                ),
                "pid": project_id,
            },
        )
        await db_session.commit()
        db_session.expire_all()  # expire_all 是同步, 强制 provision_baas 重读 DB

        schema_name = f"arc_{uuid.UUID(project_id).hex[:8]}"
        try:
            svc = DomainModelService(db_session)
            result = await svc.provision_baas(uuid.UUID(project_id))
            assert result["provisioned"] is True
            assert result["schema_name"] == schema_name

            # P0-2: RLS policy 真建出 (之前 0 -> deny-all)
            policy_count = await db_session.scalar(
                text("SELECT count(*) FROM pg_policies WHERE schemaname = :s"),
                {"s": schema_name},
            )
            assert policy_count > 0, "RLS policy 未生成 (deny-all 回归)"

            # user_id DEFAULT auth.uid() (rls_validator 检查项 2)
            col_default = await db_session.scalar(
                text(
                    "SELECT column_default FROM information_schema.columns "
                    "WHERE table_schema = :s AND table_name = 'posts' "
                    "AND column_name = 'user_id'"
                ),
                {"s": schema_name},
            )
            assert col_default is not None
            assert "auth.uid" in str(col_default)

            # baas-status 透出 provisioned
            r = await client.get(f"/api/projects/{project_id}/baas-status")
            assert r.status_code == 200
            assert r.json()["provisioned"] is True
        finally:
            await _cleanup(db_session, schema_name)
