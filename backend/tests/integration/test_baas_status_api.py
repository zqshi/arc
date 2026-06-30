"""BaaS 状态查询端点集成测试 (v6.19 续9 可观测性).

GET /api/projects/{id}/baas-status 透出 provision 是否发生 + 落地到哪,
覆盖 3 路径: 未 provision / 已 provision active (tables_count) / 项目不存在 404。

provision 走 BaasService 直调 (聚焦端点, 不走 extract 触发链路)。
cleanup: asyncpg DROP SCHEMA 持久化 (与 provision 对称, 见 test_baas_provision._cleanup_schema)。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from arc.infrastructure.baas.supabase_client import SupabaseClient


async def _ensure_supabase_roles(db_session: AsyncSession) -> None:
    """裸 PG 无 Supabase 预置 role, 测试前创建 (auth.schema 依赖)。"""
    await db_session.execute(
        text("DO $$ BEGIN CREATE ROLE authenticated; EXCEPTION WHEN duplicate_object THEN END; $$")
    )
    await db_session.execute(
        text("DO $$ BEGIN CREATE ROLE anon; EXCEPTION WHEN duplicate_object THEN END; $$")
    )
    await db_session.commit()


async def _cleanup(db_session: AsyncSession, schema_name: str) -> None:
    """asyncpg DROP SCHEMA 持久化 + 删 baas_instances 记录。"""
    client = SupabaseClient()
    try:
        await client.execute(
            f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE', schema=None
        )
    finally:
        await client.close()
    await db_session.execute(
        text("DELETE FROM baas_instances WHERE schema_name = :name"),
        {"name": schema_name},
    )
    await db_session.commit()


class TestBaasStatusApi:
    @pytest.mark.asyncio
    async def test_status_not_provisioned(self, client):
        """未 provision 的项目 -> provisioned=False + reason。"""
        resp = await client.post("/api/projects", json={"name": "Status None"})
        assert resp.status_code in (200, 201)
        project_id = resp.json()["id"]

        r = await client.get(f"/api/projects/{project_id}/baas-status")
        assert r.status_code == 200
        body = r.json()
        assert body["provisioned"] is False
        assert "reason" in body

    @pytest.mark.asyncio
    async def test_status_provisioned_active(self, client, db_session):
        """已 provision + apply_model -> provisioned=True, status=active, tables_count>=1。"""
        from arc.application.baas.service import BaasService
        from arc.domain.baas.value_objects import (
            BaasSchema,
            ColumnDef,
            TableDef,
        )

        await _ensure_supabase_roles(db_session)
        resp = await client.post("/api/projects", json={"name": "Status Provisioned"})
        assert resp.status_code in (200, 201)
        project_id = resp.json()["id"]
        schema_name = f"arc_t{uuid.uuid4().hex[:6]}"

        try:
            svc = BaasService(db_session)
            await svc.provision(
                project_id=uuid.UUID(project_id),
                schema_name=schema_name,
                supabase_url="http://localhost:54321",
            )
            await svc.apply_model(
                project_id=uuid.UUID(project_id),
                schema=BaasSchema(
                    schema_name=schema_name,
                    tables=[
                        TableDef(name="posts", columns=[
                            ColumnDef(name="id", type="uuid", is_primary=True, nullable=False),
                        ], has_rls=True),
                    ],
                    policies=[],
                ),
                model_version=1,
            )

            r = await client.get(f"/api/projects/{project_id}/baas-status")
            assert r.status_code == 200
            body = r.json()
            assert body["provisioned"] is True
            assert body["status"] == "active"
            assert body["schema_name"] == schema_name
            assert body["last_applied_model_version"] == 1
            assert body["tables_count"] >= 1  # 至少 posts 业务表
        finally:
            await _cleanup(db_session, schema_name)

    @pytest.mark.asyncio
    async def test_status_project_not_found(self, client):
        """项目不存在 -> 404。"""
        r = await client.get(f"/api/projects/{uuid.uuid4()}/baas-status")
        assert r.status_code == 404
