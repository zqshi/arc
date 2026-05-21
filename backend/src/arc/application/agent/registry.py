from __future__ import annotations

import logging

from arc.application.agent.adapter import CodingAgentAdapter
from arc.application.agent.adapters.claude_code import ClaudeCodeAdapter
from arc.application.agent.adapters.codex import CodexAdapter
from arc.application.agent.adapters.cursor import CursorAdapter
from arc.application.agent.adapters.openhands import OpenHandsAdapter
from arc.domain.agent.value_objects import AGENT_LABELS, AgentType

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Plugin registry for coding agent adapters.

    Only agents with valid configuration are registered as available.
    """

    def __init__(self):
        self._factories: dict[AgentType, callable] = {}

    def register(self, agent_type: AgentType, factory: callable) -> None:
        self._factories[agent_type] = factory
        logger.info("Registered coding agent: %s (%s)", agent_type.value, AGENT_LABELS[agent_type])

    def create(self, agent_type: AgentType) -> CodingAgentAdapter:
        factory = self._factories.get(agent_type)
        if not factory:
            raise ValueError(
                f"Agent '{agent_type.value}' is not available. "
                f"Available: {[a.value for a in self.available_agents()]}"
            )
        return factory()

    def available_agents(self) -> list[AgentType]:
        return list(self._factories.keys())

    def is_available(self, agent_type: AgentType) -> bool:
        return agent_type in self._factories


def create_agent_registry() -> AgentRegistry:
    """Build registry from application settings, only registering configured and implemented agents."""
    from arc.config import settings

    registry = AgentRegistry()

    if settings.openhands_url:
        adapter = OpenHandsAdapter()
        if adapter.implemented:
            registry.register(AgentType.OPENHANDS, lambda: OpenHandsAdapter())

    if settings.codex_api_key:
        adapter = CodexAdapter(api_key=settings.codex_api_key, base_url=settings.codex_base_url)
        if adapter.implemented:
            registry.register(
                AgentType.CODEX,
                lambda: CodexAdapter(api_key=settings.codex_api_key, base_url=settings.codex_base_url),
            )

    if settings.claude_code_path:
        adapter = ClaudeCodeAdapter(
            cli_path=settings.claude_code_path,
            work_dir=settings.claude_code_work_dir,
            model=settings.claude_code_model,
        )
        if adapter.implemented:
            registry.register(
                AgentType.CLAUDE_CODE,
                lambda: ClaudeCodeAdapter(
                    cli_path=settings.claude_code_path,
                    work_dir=settings.claude_code_work_dir,
                    model=settings.claude_code_model,
                ),
            )

    if settings.cursor_cli_path:
        adapter = CursorAdapter(cli_path=settings.cursor_cli_path)
        if adapter.implemented:
            registry.register(
                AgentType.CURSOR,
                lambda: CursorAdapter(cli_path=settings.cursor_cli_path),
            )

    return registry


agent_registry = create_agent_registry()
