"""Tests for SupabaseClient (v5.6.0 T3).

asyncpg 直连 + schema 隔离执行。测试用 mock pool 验证 SQL 执行逻辑，
不连真实 PG（集成测试 test_baas_provision.py 覆盖真实链路）。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from arc.infrastructure.baas.supabase_client import SupabaseClient


class TestSupabaseClientDsn:
    def test_explicit_dsn_used(self):
        """提供 supabase_db_url 时直接用。"""
        client = SupabaseClient(dsn="postgresql://user:pass@supabase:5432/postgres")
        assert client._dsn == "postgresql://user:pass@supabase:5432/postgres"

    def test_fallback_to_arc_database_url(self):
        """未提供 DSN 时复用 Arc 的 database_url (dev: 同库隔离)。"""
        with patch("arc.infrastructure.baas.supabase_client.settings") as mock_settings:
            mock_settings.supabase_db_url = ""
            mock_settings.database_url = "postgresql+asyncpg://zqs@localhost:5432/arc"
            client = SupabaseClient()
            # 去掉 SQLAlchemy driver 后缀, 转为纯 asyncpg DSN
            assert "asyncpg" not in client._dsn
            assert "localhost:5432" in client._dsn

    def test_explicit_dsn_overrides_fallback(self):
        with patch("arc.infrastructure.baas.supabase_client.settings") as mock_settings:
            mock_settings.supabase_db_url = "postgresql://supabase@host:5432/postgres"
            mock_settings.database_url = "postgresql+asyncpg://zqs@localhost:5432/arc"
            client = SupabaseClient()
            assert "host:5432" in client._dsn
            assert "localhost" not in client._dsn


class TestNormalizeDsn:
    """Arc 的 database_url 带 +asyncpg driver 后缀, 纯 asyncpg 需去掉。"""

    def test_strips_sqlalchemy_driver_suffix(self):
        dsn = SupabaseClient._normalize_dsn(
            "postgresql+asyncpg://user:pw@host:5432/db"
        )
        assert dsn == "postgresql://user:pw@host:5432/db"

    def test_plain_dsn_unchanged(self):
        dsn = SupabaseClient._normalize_dsn("postgresql://user:pw@host:5432/db")
        assert dsn == "postgresql://user:pw@host:5432/db"


class TestSchemaNameValidation:
    def test_valid_schema_name_accepted(self):
        """schema 名必须有 arc_ 前缀 (与 BaasSchema 约定一致)。"""
        # 不抛错即通过
        SupabaseClient._assert_valid_schema_name("arc_proj123")

    def test_invalid_prefix_rejected(self):
        with pytest.raises(ValueError, match="前缀"):
            SupabaseClient._assert_valid_schema_name("proj123")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            SupabaseClient._assert_valid_schema_name("")


class TestExecuteSql:
    """验证 SQL 在正确 search_path 下执行。"""

    @pytest.mark.asyncio
    async def test_execute_sets_search_path(self):
        """execute 应先 SET search_path 到目标 schema, 再执行 SQL。"""
        client = SupabaseClient(dsn="postgresql://u@host:5432/db")
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_conn.execute = AsyncMock()

        captured = []

        async def fake_execute(sql, *args):
            captured.append(sql)
            return "OK"

        mock_conn.execute = fake_execute

        await client.execute("SELECT 1", schema="arc_test123", conn=mock_conn)

        # 应包含 SET search_path
        joined = "\n".join(captured)
        assert "SET search_path" in joined
        assert "arc_test123" in joined
        assert "SELECT 1" in joined

    @pytest.mark.asyncio
    async def test_execute_rejects_invalid_schema(self):
        client = SupabaseClient(dsn="postgresql://u@host:5432/db")
        mock_conn = AsyncMock()

        with pytest.raises(ValueError, match="前缀"):
            await client.execute("SELECT 1", schema="bad_schema", conn=mock_conn)


class TestSchemaExists:
    @pytest.mark.asyncio
    async def test_exists_queries_pg_namespace(self):
        client = SupabaseClient(dsn="postgresql://u@host:5432/db")
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)  # schema 存在

        exists = await client.schema_exists("arc_test123", conn=mock_conn)
        assert exists is True

        # 验证查询了 pg_namespace
        sql_arg = mock_conn.fetchval.call_args[0][0]
        assert "pg_namespace" in sql_arg

    @pytest.mark.asyncio
    async def test_not_exists(self):
        client = SupabaseClient(dsn="postgresql://u@host:5432/db")
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=None)

        exists = await client.schema_exists("arc_test123", conn=mock_conn)
        assert exists is False
