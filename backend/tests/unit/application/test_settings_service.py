"""SettingsService 单元测试 — 运行时覆盖 + .env 持久化 + 缓存失效编排。"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.settings.service import SettingsService


class TestSettingsServiceApplyRuntime:
    def test_overrides_existing_field(self):
        fake = SimpleNamespace(llm_provider="openai", openai_model="gpt-4o")
        svc = SettingsService(settings_obj=fake, env_path=Path("/tmp/x"))
        svc._apply_runtime({"llm_provider": "anthropic", "openai_model": "gpt-5"})
        assert fake.llm_provider == "anthropic"
        assert fake.openai_model == "gpt-5"

    def test_skips_none_values(self):
        fake = SimpleNamespace(llm_provider="openai", openai_model="gpt-4o")
        svc = SettingsService(settings_obj=fake, env_path=Path("/tmp/x"))
        svc._apply_runtime({"llm_provider": None, "openai_model": "gpt-5"})
        assert fake.llm_provider == "openai"
        assert fake.openai_model == "gpt-5"

    def test_skips_unknown_field_silently(self):
        fake = SimpleNamespace(llm_provider="openai")
        svc = SettingsService(settings_obj=fake, env_path=Path("/tmp/x"))
        svc._apply_runtime({"nonexistent_field": "x"})
        assert not hasattr(fake, "nonexistent_field")


class TestSettingsServicePersistToEnv:
    def test_updates_existing_key_in_place(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("ARC_LLM_PROVIDER=openai\nARC_OPENAI_MODEL=gpt-4o\n")
        svc = SettingsService(env_path=env)
        svc._persist_to_env({"llm_provider": "anthropic"})
        lines = env.read_text().splitlines()
        assert "ARC_LLM_PROVIDER=anthropic" in lines
        assert "ARC_OPENAI_MODEL=gpt-4o" in lines

    def test_appends_missing_key(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("ARC_LLM_PROVIDER=openai\n")
        svc = SettingsService(env_path=env)
        svc._persist_to_env({"openai_model": "gpt-5"})
        assert "ARC_OPENAI_MODEL=gpt-5" in env.read_text().splitlines()

    def test_skips_none_values(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("ARC_LLM_PROVIDER=openai\n")
        svc = SettingsService(env_path=env)
        svc._persist_to_env({"openai_model": None, "openai_base_url": "https://x"})
        content = env.read_text()
        assert "ARC_OPENAI_BASE_URL=https://x" in content
        assert "ARC_OPENAI_MODEL" not in content

    def test_ignores_comment_lines(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("# ARC_LLM_PROVIDER=commented\nARC_LLM_PROVIDER=openai\n")
        svc = SettingsService(env_path=env)
        svc._persist_to_env({"llm_provider": "anthropic"})
        lines = env.read_text().splitlines()
        assert "# ARC_LLM_PROVIDER=commented" in lines
        assert "ARC_LLM_PROVIDER=anthropic" in lines

    def test_persists_agent_field_with_arc_prefix(self, tmp_path):
        """agent adapter 字段持久化带 ARC_ 前缀 (与 config env_prefix 一致, 重启可读回)。"""
        env = tmp_path / ".env"
        env.write_text("ARC_OPENHANDS_URL=\n")
        svc = SettingsService(env_path=env)
        svc._persist_to_env({"openhands_url": "http://oh:3000"})
        assert "ARC_OPENHANDS_URL=http://oh:3000" in env.read_text().splitlines()


class TestSettingsServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_invokes_all_steps_in_order(self, tmp_path):
        fake = SimpleNamespace(llm_provider="openai")
        svc = SettingsService(settings_obj=fake, env_path=tmp_path / ".env")
        svc._persist_to_env = MagicMock()
        svc._invalidate_adapter_cache = AsyncMock()

        result = await svc.update({"llm_provider": "anthropic"})

        assert result["status"] == "updated"
        assert result["llm_provider"] == "anthropic"
        assert result["updated_fields"] == ["llm_provider"]
        assert fake.llm_provider == "anthropic"
        svc._persist_to_env.assert_called_once()
        svc._invalidate_adapter_cache.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_llm_field_does_not_reload_registry(self, tmp_path, monkeypatch):
        """非 agent 字段更新 → registry 不 reload。"""
        fake = SimpleNamespace(llm_provider="openai")
        svc = SettingsService(settings_obj=fake, env_path=tmp_path / ".env")
        svc._invalidate_adapter_cache = AsyncMock()
        reloaded = []
        monkeypatch.setattr(
            "arc.application.agent.registry.agent_registry.reload",
            lambda: reloaded.append(1),
        )

        await svc.update({"llm_provider": "anthropic"})

        assert reloaded == []

    @pytest.mark.asyncio
    async def test_update_agent_field_reloads_registry(self, tmp_path, monkeypatch):
        """agent 字段更新 → registry.reload 被调 (skill 运行时配置生效)。"""
        fake = SimpleNamespace(llm_provider="openai", openhands_url="")
        svc = SettingsService(settings_obj=fake, env_path=tmp_path / ".env")
        svc._invalidate_adapter_cache = AsyncMock()
        reloaded = []
        monkeypatch.setattr(
            "arc.application.agent.registry.agent_registry.reload",
            lambda: reloaded.append(1),
        )

        await svc.update({"openhands_url": "http://oh:3000"})

        assert reloaded == [1]


class TestSettingsServiceResolveEnvPath:
    def test_uses_explicit_env_path(self, tmp_path):
        env = tmp_path / ".env"
        svc = SettingsService(env_path=env)
        assert svc._resolve_env_path() == env

    def test_uses_env_file_when_set(self, monkeypatch, tmp_path):
        env = tmp_path / "custom.env"
        env.write_text("X=1")
        monkeypatch.setenv("ENV_FILE", str(env))
        svc = SettingsService()
        assert svc._resolve_env_path() == env
