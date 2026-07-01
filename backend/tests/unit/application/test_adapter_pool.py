"""Unit tests for arc.application.ai.adapter_pool (v6.22 D2 worker 凭证链路)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.ai.adapter_pool import (
    _WORKER_KEY,
    AdapterPool,
    _create_worker_adapter,
)


class TestAcquireWorker:
    """v6.22 D2: worker 走 DB 凭证 (per-user 隔离), llm_config 为 None fallback env."""

    @pytest.mark.asyncio
    async def test_worker_uses_db_config_when_provided(self):
        """llm_config 有 api_key → 复用主凭证 + worker_model 覆盖 model (D2 核心)."""
        pool = AdapterPool()
        llm_config = {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "sk-db-credential",
            "base_url": "https://api.openai.com/v1",
        }

        # patch _create_worker_adapter 返回的 inner 链路
        fake_inner = MagicMock()
        fake_inner.close = AsyncMock()
        with patch(
            "arc.application.ai.adapter_pool._create_worker_adapter",
            return_value=fake_inner,
        ) as mk:
            async with pool.acquire_worker(llm_config) as adapter:
                assert adapter is not None
        # D2: _create_worker_adapter 收到 llm_config (透传)
        mk.assert_called_once_with(llm_config)
        # worker adapter 不缓存 (ephemeral, _WORKER_KEY 不被写入)
        assert _WORKER_KEY not in pool._adapters

    @pytest.mark.asyncio
    async def test_worker_fallback_env_when_config_none(self):
        """llm_config 为 None → fallback 全局 _WORKER_KEY (env 兜底, 旧行为)."""
        pool = AdapterPool()

        async with pool.acquire_worker(None) as adapter:
            assert adapter is not None
        # env 兜底走缓存路径, _WORKER_KEY 被写入
        assert _WORKER_KEY in pool._adapters

    @pytest.mark.asyncio
    async def test_worker_fallback_env_when_config_empty(self):
        """llm_config 无 api_key → 同 None, fallback env."""
        pool = AdapterPool()

        async with pool.acquire_worker({"provider": "openai", "model": "x"}) as adapter:
            assert adapter is not None
        assert _WORKER_KEY in pool._adapters

    @pytest.mark.asyncio
    async def test_worker_db_config_not_cached(self):
        """D2: DB 凭证 worker adapter 不缓存 (ephemeral), 多次 acquire 各自独立."""
        pool = AdapterPool()
        llm_config = {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "sk-x",
            "base_url": "https://api.openai.com/v1",
        }

        fake_inner = MagicMock()
        fake_inner.close = AsyncMock()
        with patch(
            "arc.application.ai.adapter_pool._create_worker_adapter",
            return_value=fake_inner,
        ):
            for _ in range(3):
                async with pool.acquire_worker(llm_config):
                    pass
        # ephemeral: DB 凭证路径不缓存, 仅 _WORKER_KEY (env 兜底) 路径才缓存
        assert _WORKER_KEY not in pool._adapters


class TestCreateWorkerAdapter:
    """_create_worker_adapter: DB 凭证复用主 config + worker_model 覆盖."""

    def test_db_config_without_worker_model_keeps_main_model(self):
        """无 settings.worker_model → worker_config.model 同主 model."""
        llm_config = {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "sk-x",
            "base_url": "https://api.openai.com/v1",
        }
        captured: dict = {}

        def fake_factory(cfg: dict):
            captured["cfg"] = cfg
            from unittest.mock import MagicMock

            return MagicMock()

        with patch(
            "arc.application.ai.llm_factory.create_llm_adapter_from_config",
            side_effect=fake_factory,
        ), patch("arc.config.settings") as mock_settings:
            mock_settings.worker_model = ""
            _create_worker_adapter(llm_config)
        assert captured["cfg"]["model"] == "gpt-4o"
        assert captured["cfg"]["api_key"] == "sk-x"

    def test_db_config_with_worker_model_overrides(self):
        """settings.worker_model 有值 → 覆盖 model (cheap model 语义)."""
        llm_config = {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "api_key": "sk-ant-x",
            "base_url": "",
        }
        captured: dict = {}

        def fake_factory(cfg: dict):
            captured["cfg"] = cfg
            from unittest.mock import MagicMock

            return MagicMock()

        with patch(
            "arc.application.ai.llm_factory.create_llm_adapter_from_config",
            side_effect=fake_factory,
        ), patch("arc.config.settings") as mock_settings:
            mock_settings.worker_model = "claude-haiku-4-5-20251001"
            _create_worker_adapter(llm_config)
        assert captured["cfg"]["model"] == "claude-haiku-4-5-20251001"
        assert captured["cfg"]["provider"] == "anthropic"
        assert captured["cfg"]["api_key"] == "sk-ant-x"
