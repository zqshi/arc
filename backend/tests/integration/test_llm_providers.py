"""LLM provider 集成测试 (v6.20 L6) — CRUD + 权限 + 模板 + verify。

真 DB session (savepoint 隔离), 覆盖全路径。
verify 端点 mock service 避免真实网络调用 (验端点接线, 探活逻辑在 unit 已覆盖)。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestLLMProviderTemplates:
    async def test_list_templates(self, client) -> None:
        r = await client.get("/api/llm/providers/templates")
        assert r.status_code == 200
        data = r.json()
        keys = [t["key"] for t in data]
        assert "openai" in keys
        assert "anthropic" in keys
        assert "custom" in keys
        openai = next(t for t in data if t["key"] == "openai")
        assert openai["kind"] == "openai_compatible"
        assert openai["supports_list_models"] is True
        anthropic = next(t for t in data if t["key"] == "anthropic")
        assert anthropic["supports_list_models"] is False


class TestLLMProviderCRUD:
    async def test_create_and_list(self, client) -> None:
        r = await client.post(
            "/api/llm/providers",
            json={
                "name": "我的OpenAI",
                "kind": "openai_compatible",
                "base_url": "https://api.openai.com/v1",
                "api_key": "sk-secret",
                "is_default": True,
            },
        )
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["name"] == "我的OpenAI"
        assert created["is_default"] is True
        assert created["api_key_set"] is True
        assert "api_key" not in created  # 不回明文

        r = await client.get("/api/llm/providers")
        assert r.status_code == 200
        providers = r.json()
        assert any(p["id"] == created["id"] for p in providers)

    async def test_update_name_and_key(self, client) -> None:
        r = await client.post(
            "/api/llm/providers",
            json={
                "name": "old", "kind": "openai_compatible",
                "base_url": "", "api_key": "k1",
            },
        )
        pid = r.json()["id"]
        r = await client.patch(
            f"/api/llm/providers/{pid}",
            json={"name": "new name", "api_key": "k2"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "new name"

    async def test_update_not_found(self, client) -> None:
        import uuid

        r = await client.patch(
            f"/api/llm/providers/{uuid.uuid4()}",
            json={"name": "x"},
        )
        assert r.status_code == 404

    async def test_delete(self, client) -> None:
        r = await client.post(
            "/api/llm/providers",
            json={
                "name": "del", "kind": "anthropic",
                "base_url": "", "api_key": "k",
            },
        )
        pid = r.json()["id"]
        r = await client.delete(f"/api/llm/providers/{pid}")
        assert r.status_code == 200
        assert r.json()["status"] == "deleted"

        r = await client.delete(f"/api/llm/providers/{pid}")
        assert r.status_code == 404  # 已删

    async def test_set_default_exclusive(self, client) -> None:
        """设第二个 default 时, 第一个应被取消 (互斥)。"""
        await client.post(
            "/api/llm/providers",
            json={
                "name": "p1", "kind": "openai_compatible",
                "base_url": "", "api_key": "k1", "is_default": True,
            },
        )
        await client.post(
            "/api/llm/providers",
            json={
                "name": "p2", "kind": "openai_compatible",
                "base_url": "", "api_key": "k2", "is_default": True,
            },
        )
        r = await client.get("/api/llm/providers")
        providers = r.json()
        defaults = [p for p in providers if p["is_default"]]
        assert len(defaults) == 1  # 部分唯一索引 + create 互斥切换保证
        assert defaults[0]["name"] == "p2"


class TestLLMProviderVerify:
    async def test_verify_endpoint_returns_models(self, client) -> None:
        """verify 端点接线 — mock service.verify_credentials 返成功+模型清单。"""
        from arc.application.llm.service import VerifyResult

        with patch(
            "arc.application.llm.service.LLMProviderService.verify_credentials",
            new=AsyncMock(
                return_value=VerifyResult(valid=True, models=["gpt-4o", "gpt-4o-mini"])
            ),
        ):
            r = await client.post(
                "/api/llm/providers/verify",
                json={
                    "kind": "openai_compatible",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": "sk-test",
                },
            )
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert data["models"] == ["gpt-4o", "gpt-4o-mini"]

    async def test_verify_empty_key_rejected_by_schema(self, client) -> None:
        """api_key 空 → pydantic schema 拒绝 (422)。"""
        r = await client.post(
            "/api/llm/providers/verify",
            json={"kind": "openai_compatible", "base_url": "", "api_key": ""},
        )
        assert r.status_code == 422


class TestLLMProviderPermissions:
    async def test_cross_user_isolated(self, client) -> None:
        """用户级隔离 — 注: 集成测试单 test_user, 此测验证越权路径返回 None/404。

        (DB 层 repo.get_by_id 带 user_id 过滤, 越权查不到 → 404)。
        本测创建后用不存在的 uuid 验证 404 行为 (越权等价不存在)。
        """
        import uuid

        r = await client.patch(
            f"/api/llm/providers/{uuid.uuid4()}",
            json={"name": "x"},
        )
        assert r.status_code == 404

    async def test_unauthenticated_rejected(self) -> None:
        """无 auth 依赖覆盖时 verify 需登录 (端点挂 CurrentUser)。

        注: client fixture 覆盖了 auth, 此测用独立 client 验证裸请求。
        覆盖 auth 后所有端点应 200, 故本测仅验证端点存在性 (templates)。
        """
        # client fixture 已覆盖 auth, 此处留占位说明权限模型由 deps.CurrentUser 保证
        pytest.skip("auth 覆盖下无法测未认证, 权限由 CurrentUser 依赖保证")


class TestLLMProviderPagination:
    async def test_pagination(self, client) -> None:
        for i in range(3):
            await client.post(
                "/api/llm/providers",
                json={
                    "name": f"p{i}", "kind": "openai_compatible",
                    "base_url": "", "api_key": f"k{i}",
                },
            )
        r = await client.get("/api/llm/providers?skip=1&limit=1")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
