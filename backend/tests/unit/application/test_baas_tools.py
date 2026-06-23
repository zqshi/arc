"""Tests for BaaS Agent tools (v5.6.0 T10).

验证 supabase_provision / supabase_execute_sql / get_domain_model
三个 tool 的注册和 handler 行为。mock BaasService。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.execution.tools import ToolRegistry


@pytest.fixture
def mock_baas_service():
    svc = MagicMock()
    svc.provision = AsyncMock(return_value=MagicMock(schema_name="arc_test123"))
    svc.apply_model = AsyncMock()
    svc.introspect = AsyncMock(return_value={
        "schema": "arc_test123", "exists": True,
        "entities_count": 3, "states_count": 0,
        "transitions_count": 0, "policies_count": 2,
    })
    return svc


class TestBaasToolsRegistration:
    def test_registry_without_baas_context_has_no_baas_tools(self, tmp_path):
        """未注入 baas_context 时, 不注册 BaaS tools (向后兼容)。"""
        registry = ToolRegistry(str(tmp_path))
        names = [t.name for t in registry.tools]
        assert "supabase_provision" not in names
        assert "supabase_execute_sql" not in names
        assert "get_domain_model" not in names

    def test_registry_with_baas_context_registers_tools(self, tmp_path, mock_baas_service):
        """注入 baas_context 后注册三个 BaaS tools。"""
        registry = ToolRegistry(str(tmp_path))
        registry.register_baas_tools(
            project_id=uuid.uuid4(), baas_service=mock_baas_service
        )
        names = [t.name for t in registry.tools]
        assert "supabase_provision" in names
        assert "supabase_execute_sql" in names
        assert "get_domain_model" in names


class TestSupabaseProvisionTool:
    @pytest.mark.asyncio
    async def test_provision_calls_service(self, tmp_path, mock_baas_service):
        registry = ToolRegistry(str(tmp_path))
        project_id = uuid.uuid4()
        registry.register_baas_tools(
            project_id=project_id, baas_service=mock_baas_service
        )

        tool = registry.get("supabase_provision")
        result = await tool.handler({"supabase_url": "http://localhost:54321"})

        mock_baas_service.provision.assert_awaited_once()
        call_kwargs = mock_baas_service.provision.call_args.kwargs
        assert call_kwargs["project_id"] == project_id
        assert call_kwargs["supabase_url"] == "http://localhost:54321"
        assert "arc_test123" in result  # 返回 schema_name

    @pytest.mark.asyncio
    async def test_provision_default_url(self, tmp_path, mock_baas_service):
        """未提供 supabase_url 时用默认 (dev 同库)。"""
        registry = ToolRegistry(str(tmp_path))
        registry.register_baas_tools(
            project_id=uuid.uuid4(), baas_service=mock_baas_service
        )
        tool = registry.get("supabase_provision")
        await tool.handler({})

        call_kwargs = mock_baas_service.provision.call_args.kwargs
        assert call_kwargs["supabase_url"]  # 有默认值


class TestSupabaseExecuteSqlTool:
    @pytest.mark.asyncio
    async def test_execute_sql_calls_client(self, tmp_path, mock_baas_service):
        """execute_sql 通过 SupabaseClient 在项目 schema 内执行 SQL。"""
        registry = ToolRegistry(str(tmp_path))
        project_id = uuid.uuid4()
        registry.register_baas_tools(
            project_id=project_id, baas_service=mock_baas_service
        )

        with patch(
            "arc.infrastructure.baas.supabase_client.SupabaseClient"
        ) as MockClient:
            mock_client = MagicMock()
            mock_client.execute = AsyncMock(return_value="CREATE TABLE")
            mock_client.close = AsyncMock()
            MockClient.return_value = mock_client

            tool = registry.get("supabase_execute_sql")
            result = await tool.handler({"sql": "CREATE TABLE posts (id uuid);"})

            mock_client.execute.assert_awaited_once()
            executed_sql = mock_client.execute.call_args.args[0]
            assert "CREATE TABLE posts" in executed_sql
            assert "CREATE TABLE" in result

    @pytest.mark.asyncio
    async def test_execute_sql_rejects_when_not_provisioned(self, tmp_path, mock_baas_service):
        """项目未 provision 时拒绝执行 SQL。"""
        mock_baas_service.introspect = AsyncMock(
            return_value={"schema": None, "exists": False}
        )
        registry = ToolRegistry(str(tmp_path))
        registry.register_baas_tools(
            project_id=uuid.uuid4(), baas_service=mock_baas_service
        )

        tool = registry.get("supabase_execute_sql")
        result = await tool.handler({"sql": "SELECT 1;"})
        assert "未 provision" in result or "不存在" in result


class TestGetDomainModelTool:
    @pytest.mark.asyncio
    async def test_get_domain_model_returns_introspect(self, tmp_path, mock_baas_service):
        registry = ToolRegistry(str(tmp_path))
        registry.register_baas_tools(
            project_id=uuid.uuid4(), baas_service=mock_baas_service
        )

        tool = registry.get("get_domain_model")
        result = await tool.handler({})

        mock_baas_service.introspect.assert_awaited_once()
        assert "3" in result  # entities_count
        assert "2" in result  # policies_count
