"""AgentRegistry 热重载单元测试 (波次2)。

验证 reload() 原地重建 (不替换单例, 对持有引用的 session_manager 透明),
按当前 settings 重新注册已配置的 agent。
"""

from __future__ import annotations

from arc.application.agent.registry import AgentRegistry, create_agent_registry
from arc.domain.agent.value_objects import AgentType


class TestAgentRegistryReload:
    def test_reload_picks_up_newly_configured_agent(self, monkeypatch):
        """settings 变更后 reload → 新配置的 agent 被注册。"""
        # 初始: openhands 未配
        monkeypatch.setattr("arc.config.settings.openhands_url", "")
        monkeypatch.setattr("arc.config.settings.codex_api_key", "")
        monkeypatch.setattr("arc.config.settings.claude_code_path", "")
        monkeypatch.setattr("arc.config.settings.cursor_cli_path", "")
        registry = create_agent_registry()
        assert AgentType.OPENHANDS not in registry.available_agents()

        # 配置 openhands → reload → 注册
        monkeypatch.setattr("arc.config.settings.openhands_url", "http://oh:3000")
        registry.reload()

        assert AgentType.OPENHANDS in registry.available_agents()
        assert registry.is_available(AgentType.OPENHANDS)

    def test_reload_drops_removed_agent(self, monkeypatch):
        """取消配置后 reload → 该 agent 不再可用 (原地重建, 非追加)。"""
        monkeypatch.setattr("arc.config.settings.openhands_url", "http://oh:3000")
        monkeypatch.setattr("arc.config.settings.codex_api_key", "")
        monkeypatch.setattr("arc.config.settings.claude_code_path", "")
        monkeypatch.setattr("arc.config.settings.cursor_cli_path", "")
        registry = create_agent_registry()
        assert AgentType.OPENHANDS in registry.available_agents()

        monkeypatch.setattr("arc.config.settings.openhands_url", "")
        registry.reload()

        assert AgentType.OPENHANDS not in registry.available_agents()

    def test_reload_preserves_instance_identity(self, monkeypatch):
        """reload 是原地重建, 同一 registry 对象 (持有引用方看到新状态)。"""
        monkeypatch.setattr("arc.config.settings.openhands_url", "")
        monkeypatch.setattr("arc.config.settings.codex_api_key", "")
        monkeypatch.setattr("arc.config.settings.claude_code_path", "")
        monkeypatch.setattr("arc.config.settings.cursor_cli_path", "")
        registry = create_agent_registry()
        original_id = id(registry)

        monkeypatch.setattr("arc.config.settings.openhands_url", "http://oh:3000")
        registry.reload()

        assert id(registry) == original_id  # 同一对象
        assert AgentType.OPENHANDS in registry.available_agents()

    def test_reload_available_agents_after_multiple_cycles(self, monkeypatch):
        """多次 reload 幂等, 不累积重复注册。"""
        monkeypatch.setattr("arc.config.settings.openhands_url", "http://oh:3000")
        monkeypatch.setattr("arc.config.settings.codex_api_key", "")
        monkeypatch.setattr("arc.config.settings.claude_code_path", "")
        monkeypatch.setattr("arc.config.settings.cursor_cli_path", "")

        registry = AgentRegistry()
        registry.reload()
        registry.reload()
        registry.reload()

        assert registry.available_agents().count(AgentType.OPENHANDS) == 1
