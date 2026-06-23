"""Tests for BaasService (v5.6.0 T7).

编排: provision + apply_model + introspect。
mock 依赖 (SupabaseClient/Provisioner/repositories), 验证编排逻辑。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.baas.entity import BaasInstance
from arc.domain.baas.value_objects import (
    ActionDef,
    BaasSchema,
    BaasStatus,
    ColumnDef,
    RlsPolicy,
    TableDef,
)
from arc.domain.errors import DomainError


def _make_schema(schema_name: str = "arc_proj123") -> BaasSchema:
    return BaasSchema(
        schema_name=schema_name,
        tables=[
            TableDef(name="posts", columns=[
                ColumnDef(name="id", type="uuid", is_primary=True, nullable=False,
                          default="gen_random_uuid()"),
                ColumnDef(name="user_id", type="uuid", nullable=False),
                ColumnDef(name="title", type="text", nullable=False),
            ], has_rls=True),
        ],
        policies=[
            RlsPolicy(table_name="posts", operation="SELECT", role="authenticated",
                      using_expr="auth.uid() = user_id"),
        ],
        transitions=[],
        actions=[],
    )


def _make_service(
    *,
    baas_repo: MagicMock | None = None,
    provisioner: MagicMock | None = None,
    client: MagicMock | None = None,
) -> "BaasService":
    from arc.application.baas.service import BaasService

    svc = BaasService.__new__(BaasService)
    svc._db = MagicMock(spec=AsyncSession)
    svc._baas_repo = baas_repo or MagicMock()
    svc._provisioner = provisioner or MagicMock()
    svc._client = client or MagicMock()
    svc._client.execute = AsyncMock(return_value="OK")
    return svc


class TestProvision:
    @pytest.mark.asyncio
    async def test_provision_new_instance(self):
        """无现有 BaasInstance → 创建 provisioning → provision → activate。"""
        baas_repo = MagicMock()
        baas_repo.get_by_project = AsyncMock(return_value=None)
        baas_repo.create = AsyncMock(side_effect=lambda i: i)
        baas_repo.update = AsyncMock(side_effect=lambda i: i)
        provisioner = MagicMock()
        provisioner.provision = AsyncMock()

        svc = _make_service(baas_repo=baas_repo, provisioner=provisioner)
        instance = await svc.provision(
            project_id=uuid.uuid4(),
            schema_name="arc_proj123",
            supabase_url="http://localhost:54321",
        )

        assert instance.status == BaasStatus.ACTIVE
        provisioner.provision.assert_awaited_once()
        baas_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_provision_existing_instance_skips(self):
        """已有 BaasInstance → 直接返回, 不重复 provision。"""
        existing = BaasInstance(
            project_id=uuid.uuid4(),
            schema_name="arc_proj123",
            supabase_url="http://localhost:54321",
            status=BaasStatus.ACTIVE,
        )
        baas_repo = MagicMock()
        baas_repo.get_by_project = AsyncMock(return_value=existing)
        provisioner = MagicMock()
        provisioner.provision = AsyncMock()

        svc = _make_service(baas_repo=baas_repo, provisioner=provisioner)
        result = await svc.provision(
            project_id=existing.project_id,
            schema_name="arc_proj123",
            supabase_url="http://localhost:54321",
        )

        assert result.id == existing.id
        provisioner.provision.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_provision_invalid_schema_name_raises(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="前缀"):
            await svc.provision(
                project_id=uuid.uuid4(),
                schema_name="bad_schema",
                supabase_url="http://localhost:54321",
            )


class TestApplyModel:
    @pytest.mark.asyncio
    async def test_apply_model_creates_tables_and_policies(self):
        """apply_model 执行: provisioner 确认 schema → 生成并执行 table/policy SQL → 更新 version。"""
        instance = BaasInstance(
            project_id=uuid.uuid4(),
            schema_name="arc_proj123",
            supabase_url="http://localhost:54321",
            status=BaasStatus.ACTIVE,
        )
        baas_repo = MagicMock()
        baas_repo.get_by_project = AsyncMock(return_value=instance)
        baas_repo.update = AsyncMock(side_effect=lambda i: i)

        svc = _make_service(baas_repo=baas_repo)
        schema = _make_schema()

        result = await svc.apply_model(
            project_id=instance.project_id, schema=schema, model_version=2
        )

        assert result.last_applied_model_version == 2
        # 验证执行了 table SQL 和 policy SQL
        executed = [c.args[0] for c in svc._client.execute.call_args_list]
        joined = "\n".join(executed)
        assert "CREATE TABLE" in joined
        assert "CREATE POLICY" in joined
        assert "posts" in joined

    @pytest.mark.asyncio
    async def test_apply_model_no_instance_raises(self):
        """未 provision 的项目不能 apply。"""
        baas_repo = MagicMock()
        baas_repo.get_by_project = AsyncMock(return_value=None)

        svc = _make_service(baas_repo=baas_repo)
        with pytest.raises(DomainError, match="未 provision"):
            await svc.apply_model(
                project_id=uuid.uuid4(), schema=_make_schema(), model_version=1
            )

    @pytest.mark.asyncio
    async def test_apply_model_version_rollback_rejected(self):
        """实体已记录 v3, 尝试 apply v2 → 实体抛错 (回退保护)。"""
        instance = BaasInstance(
            project_id=uuid.uuid4(),
            schema_name="arc_proj123",
            supabase_url="http://localhost:54321",
            status=BaasStatus.ACTIVE,
            last_applied_model_version=3,
        )
        baas_repo = MagicMock()
        baas_repo.get_by_project = AsyncMock(return_value=instance)

        svc = _make_service(baas_repo=baas_repo)
        with pytest.raises(DomainError, match="不能回退"):
            await svc.apply_model(
                project_id=instance.project_id, schema=_make_schema(), model_version=2
            )


class TestIntrospect:
    @pytest.mark.asyncio
    async def test_introspect_delegates_to_provisioner(self):
        instance = BaasInstance(
            project_id=uuid.uuid4(),
            schema_name="arc_proj123",
            supabase_url="http://localhost:54321",
            status=BaasStatus.ACTIVE,
        )
        baas_repo = MagicMock()
        baas_repo.get_by_project = AsyncMock(return_value=instance)
        provisioner = MagicMock()
        provisioner.introspect = AsyncMock(return_value={
            "schema": "arc_proj123", "exists": True, "entities_count": 5,
        })

        svc = _make_service(baas_repo=baas_repo, provisioner=provisioner)
        result = await svc.introspect(project_id=instance.project_id)

        provisioner.introspect.assert_awaited_once_with("arc_proj123")
        assert result["entities_count"] == 5

    @pytest.mark.asyncio
    async def test_introspect_no_instance(self):
        baas_repo = MagicMock()
        baas_repo.get_by_project = AsyncMock(return_value=None)

        svc = _make_service(baas_repo=baas_repo)
        result = await svc.introspect(project_id=uuid.uuid4())
        assert result["exists"] is False
