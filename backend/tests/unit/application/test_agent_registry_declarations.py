"""Tests for agent registry declarations + rebuild (v6.8.0 W2.1)."""
from __future__ import annotations

from arc.application.agent.registry import AgentRegistry, env_agent_declarations
from arc.domain.agent.value_objects import AgentType


def _clear_agent_settings(monkeypatch):
    from arc.config import settings

    monkeypatch.setattr(settings, "openhands_url", "")
    monkeypatch.setattr(settings, "openhands_api_key", "")
    monkeypatch.setattr(settings, "codex_api_key", "")
    monkeypatch.setattr(settings, "codex_base_url", "https://api.openai.com/v1")
    monkeypatch.setattr(settings, "claude_code_path", "")
    monkeypatch.setattr(settings, "cursor_cli_path", "")


class TestEnvAgentDeclarations:
    def test_openhands_configured(self, monkeypatch):
        _clear_agent_settings(monkeypatch)
        from arc.config import settings

        monkeypatch.setattr(settings, "openhands_url", "http://x:3000")
        decls = env_agent_declarations()
        types = [t for t, _ in decls]
        assert types == [AgentType.OPENHANDS]
        assert decls[0][1] == {"url": "http://x:3000"}

    def test_codex_configured(self, monkeypatch):
        _clear_agent_settings(monkeypatch)
        from arc.config import settings

        monkeypatch.setattr(settings, "codex_api_key", "sk-x")
        monkeypatch.setattr(settings, "codex_base_url", "https://api.x.com/v1")
        decls = env_agent_declarations()
        codex = [d for d in decls if d[0] == AgentType.CODEX]
        assert len(codex) == 1
        assert codex[0][1] == {"api_key": "sk-x", "base_url": "https://api.x.com/v1"}

    def test_none_configured_returns_empty(self, monkeypatch):
        _clear_agent_settings(monkeypatch)
        assert env_agent_declarations() == []


class TestRebuild:
    def test_rebuild_registers_configured(self):
        registry = AgentRegistry()
        registry.rebuild([(AgentType.OPENHANDS, {"url": "http://x:3000"})])
        assert AgentType.OPENHANDS in registry.available_agents()

    def test_rebuild_skips_unconfigured(self):
        registry = AgentRegistry()
        registry.rebuild([(AgentType.OPENHANDS, {})])  # url 空 → 不注册
        assert registry.available_agents() == []

    def test_rebuild_replaces_previous(self):
        registry = AgentRegistry()
        registry.rebuild([(AgentType.OPENHANDS, {"url": "http://x:3000"})])
        registry.rebuild([])  # 清空
        assert registry.available_agents() == []

    def test_reload_uses_env(self, monkeypatch):
        _clear_agent_settings(monkeypatch)
        from arc.config import settings

        monkeypatch.setattr(settings, "openhands_url", "http://x:3000")
        registry = AgentRegistry()
        registry.reload()
        assert AgentType.OPENHANDS in registry.available_agents()
