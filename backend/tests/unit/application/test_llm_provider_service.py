"""LLM provider service 单元测试 (v6.20 L4)。

mock repository (ABC) + patch _build_adapter 返 mock adapter (不依赖真实 SDK/网络)。
覆盖 CRUD 编排 + verify_credentials (临时凭证探活) + list_models (缓存回填)。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.llm.service import LLMProviderService, VerifyResult
from arc.domain.llm.entity import LLMProvider
from arc.domain.llm.value_objects import LLMProviderKind


def _make_provider(
    *,
    kind: LLMProviderKind = LLMProviderKind.OPENAI_COMPATIBLE,
    api_key_enc: str = "enc(token)",
    models: list[str] | None = None,
    is_default: bool = False,
) -> LLMProvider:
    return LLMProvider(
        user_id=uuid.uuid4(),
        name="我的OpenAI",
        kind=kind,
        base_url="https://api.openai.com/v1",
        api_key_enc=api_key_enc,
        models=models or [],
        is_default=is_default,
    )


class _FakeRepo:
    """手写 fake repo (记录调用, 不依赖 DB)。"""

    def __init__(self) -> None:
        self.providers: dict[uuid.UUID, LLMProvider] = {}
        self.default_set_for: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def create(self, provider: LLMProvider) -> LLMProvider:
        self.providers[provider.id] = provider
        return provider

    async def get_by_id(self, provider_id, user_id) -> LLMProvider | None:
        p = self.providers.get(provider_id)
        if p and p.user_id == user_id:
            return p
        return None

    async def list_by_user(self, user_id, *, skip=0, limit=50) -> list[LLMProvider]:
        return [p for p in self.providers.values() if p.user_id == user_id]

    async def get_default(self, user_id) -> LLMProvider | None:
        defaults = [p for p in self.providers.values() if p.user_id == user_id and p.is_default]
        return defaults[0] if defaults else None

    async def update(self, provider: LLMProvider) -> None:
        self.providers[provider.id] = provider

    async def delete(self, provider_id, user_id) -> bool:
        p = self.providers.get(provider_id)
        if p and p.user_id == user_id:
            del self.providers[provider_id]
            return True
        return False

    async def set_default(self, provider_id, user_id) -> None:
        self.default_set_for.append((provider_id, user_id))

    async def count_by_user(self, user_id) -> int:
        return sum(1 for p in self.providers.values() if p.user_id == user_id)


class TestLLMProviderCRUD:
    async def test_create_encrypts_api_key(self) -> None:
        repo = _FakeRepo()
        svc = LLMProviderService(repo)
        with patch("arc.application.llm.service._encrypt", side_effect=lambda x: f"enc({x})"):
            p = await svc.create(
                user_id=uuid.uuid4(),
                name="openai",
                kind=LLMProviderKind.OPENAI_COMPATIBLE,
                base_url="https://api.openai.com/v1",
                api_key="sk-secret",
            )
        assert p.api_key_enc == "enc(sk-secret)"

    async def test_create_default_sets_default(self) -> None:
        repo = _FakeRepo()
        svc = LLMProviderService(repo)
        with patch("arc.application.llm.service._encrypt", side_effect=lambda x: f"enc({x})"):
            p = await svc.create(
                user_id=uuid.uuid4(),
                name="openai",
                kind=LLMProviderKind.OPENAI_COMPATIBLE,
                base_url="",
                api_key="sk-secret",
                is_default=True,
            )
        assert p.is_default is True
        assert repo.default_set_for == [(p.id, p.user_id)]

    async def test_update_renames(self) -> None:
        repo = _FakeRepo()
        svc = LLMProviderService(repo)
        with patch("arc.application.llm.service._encrypt", side_effect=lambda x: f"enc({x})"):
            p = await svc.create(
                user_id=uuid.uuid4(), name="old", kind=LLMProviderKind.OPENAI_COMPATIBLE,
                base_url="u", api_key="k",
            )
        updated = await svc.update(p.id, p.user_id, name="new name")
        assert updated.name == "new name"

    async def test_update_not_found_raises(self) -> None:
        repo = _FakeRepo()
        svc = LLMProviderService(repo)
        with pytest.raises(ValueError, match="not found"):
            await svc.update(uuid.uuid4(), uuid.uuid4(), name="x")

    async def test_delete(self) -> None:
        repo = _FakeRepo()
        svc = LLMProviderService(repo)
        with patch("arc.application.llm.service._encrypt", side_effect=lambda x: f"enc({x})"):
            p = await svc.create(
                user_id=uuid.uuid4(), name="x", kind=LLMProviderKind.OPENAI_COMPATIBLE,
                base_url="", api_key="k",
            )
        assert await svc.delete(p.id, p.user_id) is True
        assert await svc.delete(uuid.uuid4(), p.user_id) is False


class TestVerifyCredentials:
    async def test_empty_key_returns_invalid(self) -> None:
        svc = LLMProviderService(_FakeRepo())
        result = await svc.verify_credentials(
            kind=LLMProviderKind.OPENAI_COMPATIBLE, base_url="", api_key=""
        )
        assert result.valid is False
        assert result.error_kind == "invalid_key"

    async def test_openai_success_returns_models(self) -> None:
        svc = LLMProviderService(_FakeRepo())
        mock_adapter = MagicMock()
        mock_adapter.list_models = AsyncMock(return_value=["gpt-4o", "gpt-4o-mini"])
        mock_adapter.close = AsyncMock()
        with patch.object(svc, "_build_adapter", return_value=mock_adapter):
            result = await svc.verify_credentials(
                kind=LLMProviderKind.OPENAI_COMPATIBLE,
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
            )
        assert result.valid is True
        assert result.models == ["gpt-4o", "gpt-4o-mini"]
        mock_adapter.close.assert_awaited()

    async def test_anthropic_success_verifies_then_static(self) -> None:
        svc = LLMProviderService(_FakeRepo())
        mock_adapter = MagicMock()
        mock_adapter.verify = AsyncMock()
        mock_adapter.list_models = AsyncMock(
            return_value=["claude-sonnet-4-6", "claude-opus-4-8"]
        )
        mock_adapter.close = AsyncMock()
        with patch.object(svc, "_build_adapter", return_value=mock_adapter):
            result = await svc.verify_credentials(
                kind=LLMProviderKind.ANTHROPIC,
                base_url="",
                api_key="sk-test",
            )
        assert result.valid is True
        mock_adapter.verify.assert_awaited()  # Anthropic 先探活
        assert "claude-sonnet-4-6" in result.models

    async def test_invalid_key_classified(self) -> None:
        svc = LLMProviderService(_FakeRepo())
        mock_adapter = MagicMock()
        exc = RuntimeError("Unauthorized")
        exc.status_code = 401  # type: ignore[attr-defined]
        mock_adapter.list_models = AsyncMock(side_effect=exc)
        mock_adapter.close = AsyncMock()
        with patch.object(svc, "_build_adapter", return_value=mock_adapter):
            result = await svc.verify_credentials(
                kind=LLMProviderKind.OPENAI_COMPATIBLE, base_url="", api_key="sk-bad"
            )
        assert result.valid is False
        assert result.error_kind == "invalid_key"

    async def test_network_error_classified(self) -> None:
        svc = LLMProviderService(_FakeRepo())
        mock_adapter = MagicMock()
        mock_adapter.list_models = AsyncMock(
            side_effect=ConnectionError("connect refused")
        )
        mock_adapter.close = AsyncMock()
        with patch.object(svc, "_build_adapter", return_value=mock_adapter):
            result = await svc.verify_credentials(
                kind=LLMProviderKind.OPENAI_COMPATIBLE, base_url="", api_key="sk-test"
            )
        assert result.valid is False
        assert result.error_kind == "network"

    async def test_close_called_on_failure(self) -> None:
        """探活失败也必须 close adapter (资源释放)。"""
        svc = LLMProviderService(_FakeRepo())
        mock_adapter = MagicMock()
        mock_adapter.list_models = AsyncMock(side_effect=RuntimeError("500"))
        mock_adapter.close = AsyncMock()
        with patch.object(svc, "_build_adapter", return_value=mock_adapter):
            await svc.verify_credentials(
                kind=LLMProviderKind.OPENAI_COMPATIBLE, base_url="", api_key="sk-test"
            )
        mock_adapter.close.assert_awaited()


class TestListModelsCache:
    async def test_returns_cached_models_without_fetch(self) -> None:
        repo = _FakeRepo()
        svc = LLMProviderService(repo)
        uid = uuid.uuid4()
        with patch("arc.application.llm.service._encrypt", side_effect=lambda x: f"enc({x})"):
            p = await svc.create(
                user_id=uid, name="x", kind=LLMProviderKind.OPENAI_COMPATIBLE,
                base_url="u", api_key="k",
            )
        p.set_models(["cached-model"])
        await repo.update(p)
        # 无 refresh → 返缓存, 不调 adapter
        models = await svc.list_models(p.id, uid)
        assert models == ["cached-model"]

    async def test_refresh_fetches_and_persists(self) -> None:
        repo = _FakeRepo()
        svc = LLMProviderService(repo)
        uid = uuid.uuid4()
        with patch("arc.application.llm.service._encrypt", side_effect=lambda x: f"enc({x})"), \
             patch("arc.application.llm.service._decrypt", side_effect=lambda x: x.removeprefix("enc(")):
            p = await svc.create(
                user_id=uid, name="x", kind=LLMProviderKind.OPENAI_COMPATIBLE,
                base_url="u", api_key="k",
            )
        mock_adapter = MagicMock()
        mock_adapter.list_models = AsyncMock(return_value=["gpt-4o", "gpt-4o-mini"])
        mock_adapter.close = AsyncMock()
        with patch.object(svc, "_build_adapter", return_value=mock_adapter):
            models = await svc.list_models(p.id, uid, refresh=True)
        assert models == ["gpt-4o", "gpt-4o-mini"]
        # 缓存回填
        updated = await repo.get_by_id(p.id, uid)
        assert updated.models == ["gpt-4o", "gpt-4o-mini"]

    async def test_not_found_raises(self) -> None:
        svc = LLMProviderService(_FakeRepo())
        with pytest.raises(ValueError, match="not found"):
            await svc.list_models(uuid.uuid4(), uuid.uuid4())

    async def test_no_api_key_returns_existing_cache(self) -> None:
        """provider 无 api_key → 返已有缓存 (不抛, graceful)。"""
        repo = _FakeRepo()
        svc = LLMProviderService(repo)
        uid = uuid.uuid4()
        with patch("arc.application.llm.service._encrypt", side_effect=lambda x: f"enc({x})"):
            p = await svc.create(
                user_id=uid, name="x", kind=LLMProviderKind.OPENAI_COMPATIBLE,
                base_url="u", api_key="",
            )
        p.set_models(["old"])
        await repo.update(p)
        models = await svc.list_models(p.id, uid, refresh=True)
        assert models == ["old"]  # 无 key 不拉取, 返缓存


class TestVerifyResult:
    def test_defaults(self) -> None:
        r = VerifyResult(valid=True)
        assert r.models == []
        assert r.error_kind == ""
