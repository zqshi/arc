"""Tests for DomainModelApplier (v5.6.0 T8).

DomainModelSnapshot.content → BaasSchema 转换。
mock BaasService, 验证转换逻辑 (不测真实 apply)。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.domain.baas.value_objects import BaasSchema
from arc.domain.project.value_objects import DomainModelSnapshot, ModelChangeTrigger


def _make_snapshot(aggregates: list[dict], version: int = 1) -> DomainModelSnapshot:
    return DomainModelSnapshot(
        version=version,
        content={"aggregates": aggregates, "relations": [], "subdomains": [], "contexts": []},
        trigger=ModelChangeTrigger.MANUAL,
        trigger_todo_id="todo-1",
        created_at=datetime.now(UTC),
    )


class TestConvertToBaasSchema:
    def test_basic_aggregate_to_table(self):
        """单个聚合 → 单张表, 聚合字段 → 列。"""
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([
            {"name": "Post", "fields": ["id", "title", "user_id"]},
        ])
        project_id = uuid.uuid4()

        schema = DomainModelApplier.convert_to_baas_schema(
            snapshot, project_id=project_id
        )

        assert isinstance(schema, BaasSchema)
        assert schema.schema_name.startswith("arc_")
        assert len(schema.tables) == 1
        table = schema.tables[0]
        assert table.name == "posts"  # 表名小写复数
        col_names = [c.name for c in table.columns]
        assert "id" in col_names
        assert "title" in col_names
        assert "user_id" in col_names

    def test_id_column_becomes_primary_key(self):
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([
            {"name": "Post", "fields": ["id", "title"]},
        ])

        schema = DomainModelApplier.convert_to_baas_schema(
            snapshot, project_id=uuid.uuid4()
        )
        pk_cols = [c for c in schema.tables[0].columns if c.is_primary]
        assert len(pk_cols) == 1
        assert pk_cols[0].name == "id"
        assert pk_cols[0].type == "uuid"
        assert pk_cols[0].nullable is False

    def test_missing_id_field_gets_auto_pk(self):
        """聚合无 id 字段时自动补 uuid 主键。"""
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([
            {"name": "Tag", "fields": ["name"]},
        ])

        schema = DomainModelApplier.convert_to_baas_schema(
            snapshot, project_id=uuid.uuid4()
        )
        # 应自动补 id
        col_names = [c.name for c in schema.tables[0].columns]
        assert "id" in col_names

    def test_default_rls_enabled(self):
        """生成的表默认启用 RLS。"""
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([
            {"name": "Post", "fields": ["id"]},
        ])

        schema = DomainModelApplier.convert_to_baas_schema(
            snapshot, project_id=uuid.uuid4()
        )
        assert schema.tables[0].has_rls is True

    def test_schema_name_derived_from_project_id(self):
        """schema_name = arc_ + project_id 前 8 位。"""
        from arc.application.baas.domain_model_applier import DomainModelApplier

        project_id = uuid.UUID("12345678-aaaa-bbbb-cccc-1234567890ab")
        snapshot = _make_snapshot([{"name": "Post", "fields": ["id"]}])

        schema = DomainModelApplier.convert_to_baas_schema(
            snapshot, project_id=project_id
        )
        assert schema.schema_name == "arc_12345678"

    def test_empty_aggregates_produces_empty_schema(self):
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([])
        schema = DomainModelApplier.convert_to_baas_schema(
            snapshot, project_id=uuid.uuid4()
        )
        assert schema.tables == []

    def test_multiple_aggregates(self):
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([
            {"name": "Post", "fields": ["id", "title"]},
            {"name": "Comment", "fields": ["id", "content"]},
        ])

        schema = DomainModelApplier.convert_to_baas_schema(
            snapshot, project_id=uuid.uuid4()
        )
        assert len(schema.tables) == 2
        table_names = [t.name for t in schema.tables]
        assert "posts" in table_names
        assert "comments" in table_names

    def test_user_id_column_gets_auth_uid_default(self):
        """user_id 列 DEFAULT auth.uid() — 防前端伪造 owner (rls_validator 检查项 2)。"""
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([{"name": "Post", "fields": ["id", "title", "user_id"]}])
        schema = DomainModelApplier.convert_to_baas_schema(snapshot, project_id=uuid.uuid4())
        user_id_col = next(c for c in schema.tables[0].columns if c.name == "user_id")
        assert user_id_col.default == "auth.uid()"

    def test_user_id_table_generates_row_isolation_policies(self):
        """有 user_id 的表生成 authenticated 行级隔离策略 (user_id = auth.uid())。

        v6.24 P0-2: 之前 policies=[] 导致 RLS 启用但 deny-all。
        """
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([{"name": "Post", "fields": ["id", "user_id"]}])
        schema = DomainModelApplier.convert_to_baas_schema(snapshot, project_id=uuid.uuid4())
        table = schema.tables[0]
        ops = {(p.operation, p.role) for p in schema.policies if p.table_name == table.name}
        assert ("SELECT", "authenticated") in ops
        assert ("INSERT", "authenticated") in ops
        assert ("UPDATE", "authenticated") in ops
        assert ("DELETE", "authenticated") in ops
        sel = next(p for p in schema.policies if p.table_name == table.name and p.operation == "SELECT")
        assert sel.using_expr == "user_id = auth.uid()"
        ins = next(p for p in schema.policies if p.table_name == table.name and p.operation == "INSERT")
        assert ins.check_expr == "user_id = auth.uid()"  # WITH CHECK 防越权写入

    def test_no_user_id_table_generates_authenticated_shared_policies(self):
        """无 user_id 表 (字典表) 生成 authenticated 共享策略 — 非 anon 全放行, 非 deny。"""
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([{"name": "Tag", "fields": ["id", "name"]}])
        schema = DomainModelApplier.convert_to_baas_schema(snapshot, project_id=uuid.uuid4())
        table = schema.tables[0]
        policies = [p for p in schema.policies if p.table_name == table.name]
        assert len(policies) > 0  # 非 deny-all
        assert all(p.role == "authenticated" for p in policies)  # 非 anon

    def test_generated_schema_passes_rls_validation(self):
        """端到端安全闭环: convert 产出经 validate_rls 无 warning。"""
        from arc.application.baas.domain_model_applier import DomainModelApplier
        from arc.application.baas.rls_validator import validate_rls

        snapshot = _make_snapshot([
            {"name": "Post", "fields": ["id", "title", "user_id"]},
            {"name": "Tag", "fields": ["id", "name"]},
        ])
        schema = DomainModelApplier.convert_to_baas_schema(snapshot, project_id=uuid.uuid4())
        warnings = validate_rls(schema)
        assert warnings == [], f"RLS 校验有 warning: {[ (w.table, w.message) for w in warnings]}"


class TestApplySnapshot:
    @pytest.mark.asyncio
    async def test_apply_calls_baas_service(self):
        """apply_snapshot: convert → baas_service.provision → apply_model。"""
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([{"name": "Post", "fields": ["id", "title"]}])
        project_id = uuid.uuid4()

        baas_service = MagicMock()
        baas_service.provision = AsyncMock(return_value=MagicMock())
        baas_service.apply_model = AsyncMock()

        applier = DomainModelApplier(baas_service)
        await applier.apply_snapshot(
            project_id=project_id, snapshot=snapshot,
            supabase_url="http://localhost:54321",
        )

        baas_service.provision.assert_awaited_once()
        baas_service.apply_model.assert_awaited_once()
        # apply_model 收到的是 BaasSchema
        call_kwargs = baas_service.apply_model.call_args.kwargs
        assert isinstance(call_kwargs["schema"], BaasSchema)
        assert call_kwargs["model_version"] == snapshot.version

    @pytest.mark.asyncio
    async def test_apply_skips_when_no_aggregates(self):
        """无聚合的空模型不 provision (无意义的空 schema)。"""
        from arc.application.baas.domain_model_applier import DomainModelApplier

        snapshot = _make_snapshot([])
        baas_service = MagicMock()
        baas_service.provision = AsyncMock()
        baas_service.apply_model = AsyncMock()

        applier = DomainModelApplier(baas_service)
        result = await applier.apply_snapshot(
            project_id=uuid.uuid4(), snapshot=snapshot,
            supabase_url="http://localhost:54321",
        )

        assert result is None  # 跳过
        baas_service.provision.assert_not_awaited()
