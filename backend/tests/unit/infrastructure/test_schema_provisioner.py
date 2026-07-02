"""Tests for schema_provisioner (v5.6.0 T4).

验证 provision 流程: CREATE SCHEMA + 元模型表初始化。
用 mock SupabaseClient 验证执行序列, 真实链路由集成测试覆盖。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.domain.baas.errors import ProvisionError
from arc.infrastructure.baas.schema_provisioner import SchemaProvisioner


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.execute = AsyncMock(return_value="CREATE SCHEMA")
    client.schema_exists = AsyncMock(return_value=False)
    client.fetchval = AsyncMock(return_value=None)
    return client


@pytest.fixture
def provisioner(mock_client):
    return SchemaProvisioner(mock_client)


class TestProvision:
    @pytest.mark.asyncio
    async def test_provision_creates_schema_and_meta(self, provisioner, mock_client):
        await provisioner.provision("arc_test123")

        # 验证执行了 CREATE SCHEMA
        executed_sql = [c.args[0] for c in mock_client.execute.call_args_list]
        joined = "\n".join(executed_sql)
        assert "CREATE SCHEMA" in joined
        assert "_meta_entities" in joined  # 元模型表

    @pytest.mark.asyncio
    async def test_provision_skips_existing_schema(self, provisioner, mock_client):
        """schema 已存在则跳过 CREATE SCHEMA, 仍确保元模型表 (IF NOT EXISTS 幂等)。"""
        mock_client.schema_exists = AsyncMock(return_value=True)

        await provisioner.provision("arc_test123")

        # 不应再 CREATE 目标 SCHEMA (arc_test123); auth schema 兼容兜底除外 (v6.24 P0-2)
        executed_sql = [c.args[0] for c in mock_client.execute.call_args_list]
        schema_creates = [s for s in executed_sql if "CREATE SCHEMA" in s and "arc_test123" in s]
        assert len(schema_creates) == 0
        # 但元模型表仍执行 (IF NOT EXISTS 幂等)
        assert any("_meta_entities" in s for s in executed_sql)
        # v6.24 P0-2: Supabase 兼容兜底 (roles + auth.uid) 始终执行
        assert any("authenticated" in s for s in executed_sql)
        assert any("auth.uid" in s for s in executed_sql)

    @pytest.mark.asyncio
    async def test_provision_invalid_schema_raises(self, provisioner):
        with pytest.raises(ValueError, match="前缀"):
            await provisioner.provision("bad_schema")

    @pytest.mark.asyncio
    async def test_provision_wraps_db_error(self, provisioner, mock_client):
        """DB 执行错误应包装为 ProvisionError (领域语义)。"""
        mock_client.execute = AsyncMock(side_effect=Exception("connection refused"))

        with pytest.raises(ProvisionError, match="connection refused"):
            await provisioner.provision("arc_test123")


class TestIntrospect:
    @pytest.mark.asyncio
    async def test_introspect_returns_schema_info(self, provisioner, mock_client):
        """introspect 读取元模型表, 返回当前 schema 的领域结构。"""
        mock_client.schema_exists = AsyncMock(return_value=True)
        mock_client.fetchval = AsyncMock(
            side_effect=[
                3,  # _meta_entities count
                5,  # _meta_states count
                2,  # _meta_transitions count
                4,  # _meta_policies count
            ]
        )

        info = await provisioner.introspect("arc_test123")
        assert info["schema"] == "arc_test123"
        assert info["exists"] is True
        assert info["entities_count"] == 3
        assert info["states_count"] == 5
        assert info["transitions_count"] == 2
        assert info["policies_count"] == 4

    @pytest.mark.asyncio
    async def test_introspect_nonexistent_schema(self, provisioner, mock_client):
        mock_client.schema_exists = AsyncMock(return_value=False)
        mock_client.fetchval = AsyncMock(return_value=None)

        info = await provisioner.introspect("arc_test123")
        assert info["exists"] is False
