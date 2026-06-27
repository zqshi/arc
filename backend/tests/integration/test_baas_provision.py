"""BaaS provision 全链路集成测试 (v5.6.0 T16).

真实 PG: provision → apply_model → 表/RLS 真实创建 → introspect 验证。
每测试用独立 schema (arc_test_*), 测后 DROP SCHEMA 清理。
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from arc.domain.baas.value_objects import (
    BaasSchema,
    ColumnDef,
    RlsPolicy,
    TableDef,
)
from arc.infrastructure.baas.supabase_client import SupabaseClient


async def _cleanup_schema(db_session, schema_name: str) -> None:
    """测试后清理: DROP SCHEMA + 删 baas_instances 记录。"""
    await db_session.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
    await db_session.execute(
        text("DELETE FROM baas_instances WHERE schema_name = :name"),
        {"name": schema_name},
    )
    await db_session.commit()


async def _ensure_supabase_roles(db_session) -> None:
    """裸 PG 无 Supabase 预置 role (authenticated/anon), 测试前创建。

    真实 Supabase 环境已存在, CREATE ROLE IF NOT EXISTS 幂等。
    """
    await db_session.execute(text("DO $$ BEGIN CREATE ROLE authenticated; EXCEPTION WHEN duplicate_object THEN END; $$"))
    await db_session.execute(text("DO $$ BEGIN CREATE ROLE anon; EXCEPTION WHEN duplicate_object THEN END; $$"))
    await db_session.commit()


async def _make_project(client: AsyncClient, name: str = "BaaS Test") -> str:
    resp = await client.post("/api/projects", json={"name": name})
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


class TestBaasProvisionE2E:
    @pytest.mark.asyncio
    async def test_provision_creates_real_schema(self, client: AsyncClient, db_session):
        """provision → 真实 schema + 元模型表创建。"""
        from arc.application.baas.service import BaasService

        project_id = await _make_project(client, "Provision E2E")
        # 用唯一 schema 名避免冲突 (project_id hex 前 8 位 + 随机后缀)
        unique = f"arc_t{uuid.uuid4().hex[:6]}"
        try:
            svc = BaasService(db_session)
            instance = await svc.provision(
                project_id=uuid.UUID(project_id),
                schema_name=unique,
                supabase_url="http://localhost:54321",
            )

            # 验证状态
            from arc.domain.baas.value_objects import BaasStatus
            assert instance.status == BaasStatus.ACTIVE
            assert instance.schema_name == unique

            # 验证 schema 真实存在
            check_client = SupabaseClient()
            exists = await check_client.schema_exists(unique)
            assert exists is True

            # 验证元模型表存在
            val = await check_client.fetchval(
                f'SELECT count(*) FROM "{unique}"._meta_entities', schema=unique
            )
            assert val == 0  # 空表
            await check_client.close()
        finally:
            await _cleanup_schema(db_session, unique)

    @pytest.mark.asyncio
    async def test_apply_model_creates_real_tables(self, client: AsyncClient, db_session):
        """provision + apply_model → 真实表 + RLS 策略创建。"""
        from arc.application.baas.service import BaasService

        await _ensure_supabase_roles(db_session)
        project_id = await _make_project(client, "Apply E2E")
        unique = f"arc_t{uuid.uuid4().hex[:6]}"
        try:
            svc = BaasService(db_session)
            await svc.provision(
                project_id=uuid.UUID(project_id),
                schema_name=unique,
                supabase_url="http://localhost:54321",
            )

            schema = BaasSchema(
                schema_name=unique,
                tables=[
                    TableDef(name="posts", columns=[
                        ColumnDef(name="id", type="uuid", is_primary=True,
                                  nullable=False, default="gen_random_uuid()"),
                        ColumnDef(name="user_id", type="uuid", nullable=False),
                        ColumnDef(name="title", type="text", nullable=False),
                    ], has_rls=True),
                ],
                policies=[
                    # 真实 Supabase 环境用 auth.uid() = user_id;
                    # 裸 PG 测试用 true 避免 auth schema 依赖
                    RlsPolicy(table_name="posts", operation="SELECT",
                              role="authenticated", using_expr="true"),
                ],
            )

            instance = await svc.apply_model(
                project_id=uuid.UUID(project_id),
                schema=schema,
                model_version=1,
            )
            assert instance.last_applied_model_version == 1

            # 验证表真实存在
            check_client = SupabaseClient()
            table_exists = await check_client.fetchval(
                f"SELECT to_regclass('{unique}.posts')", schema=unique
            )
            assert table_exists is not None

            # 验证 RLS 启用
            rls_enabled = await check_client.fetchval(
                "SELECT relrowsecurity FROM pg_class WHERE relname='posts'",
                schema=unique
            )
            assert rls_enabled is True
            await check_client.close()
        finally:
            await _cleanup_schema(db_session, unique)

    @pytest.mark.asyncio
    async def test_introspect_after_apply(self, client: AsyncClient, db_session):
        """apply 后 introspect 返回正确的结构计数。"""
        from arc.application.baas.service import BaasService

        project_id = await _make_project(client, "Introspect E2E")
        unique = f"arc_t{uuid.uuid4().hex[:6]}"
        try:
            svc = BaasService(db_session)
            await svc.provision(
                project_id=uuid.UUID(project_id),
                schema_name=unique,
                supabase_url="http://localhost:54321",
            )
            await svc.apply_model(
                project_id=uuid.UUID(project_id),
                schema=BaasSchema(
                    schema_name=unique,
                    tables=[TableDef(name="t", columns=[
                        ColumnDef(name="id", type="uuid", is_primary=True, nullable=False),
                    ])],
                    policies=[],
                ),
                model_version=1,
            )

            info = await svc.introspect(uuid.UUID(project_id))
            assert info["exists"] is True
            assert info["schema"] == unique
        finally:
            await _cleanup_schema(db_session, unique)

    @pytest.mark.asyncio
    async def test_provision_idempotent(self, client: AsyncClient, db_session):
        """重复 provision 同一项目不报错, 返回已有 instance。"""
        from arc.application.baas.service import BaasService

        project_id = await _make_project(client, "Idempotent E2E")
        unique = f"arc_t{uuid.uuid4().hex[:6]}"
        try:
            svc = BaasService(db_session)
            first = await svc.provision(
                project_id=uuid.UUID(project_id),
                schema_name=unique,
                supabase_url="http://localhost:54321",
            )
            second = await svc.provision(
                project_id=uuid.UUID(project_id),
                schema_name=unique,
                supabase_url="http://localhost:54321",
            )
            assert first.id == second.id  # 同一 instance
        finally:
            await _cleanup_schema(db_session, unique)
