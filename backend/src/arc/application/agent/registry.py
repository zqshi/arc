from __future__ import annotations

import logging
import uuid

from arc.application.agent.adapter import CodingAgentAdapter
from arc.application.agent.adapters.claude_code import ClaudeCodeAdapter
from arc.application.agent.adapters.codex import CodexAdapter
from arc.application.agent.adapters.cursor import CursorAdapter
from arc.application.agent.adapters.openhands import OpenHandsAdapter
from arc.domain.agent.value_objects import AGENT_LABELS, AgentType

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Plugin registry for coding agent adapters.

    v6.8 W2.1: 声明驱动 — rebuild(declarations) 按 (AgentType, config) 构造 adapter;
    env_agent_declarations() 从 settings 生成声明 (env 兜底); sync_registry_from_db()
    从 DB 声明同步 (DB 空 → seed env → reload)。
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

    def rebuild(self, declarations: list[tuple[AgentType, dict]]) -> None:
        """按声明 (AgentType, config) 原地重建 — 清空并重新注册。

        declarations 来自 env (env_agent_declarations) 或 DB (sync_registry_from_db)。
        不替换单例对象, 持有 registry 引用的调用方自动看到新状态。
        """
        self._factories.clear()
        for agent_type, config in declarations:
            factory = _build_factory(agent_type, config)
            if factory is not None:
                self.register(agent_type, factory)

    def reload(self) -> None:
        """原地重建: 按当前 settings (env) 重新注册。

        env 兜底路径 — DB 空 或 settings 运行时变更后调用。
        """
        self.rebuild(env_agent_declarations())


def env_agent_declarations() -> list[tuple[AgentType, dict]]:
    """从 settings 生成已配置 agent 的声明 (env 兜底来源)。

    config 存该 agent 构造参数: openhands={url} / codex={api_key, base_url} /
    claude_code={cli_path, work_dir, model} / cursor={cli_path}。
    未配置 (关键字段空) 不生成。
    """
    from arc.config import settings

    declarations: list[tuple[AgentType, dict]] = []
    if settings.openhands_url:
        declarations.append((AgentType.OPENHANDS, {"url": settings.openhands_url}))
    if settings.codex_api_key:
        declarations.append(
            (
                AgentType.CODEX,
                {"api_key": settings.codex_api_key, "base_url": settings.codex_base_url},
            )
        )
    if settings.claude_code_path:
        declarations.append(
            (
                AgentType.CLAUDE_CODE,
                {
                    "cli_path": settings.claude_code_path,
                    "work_dir": settings.claude_code_work_dir,
                    "model": settings.claude_code_model,
                },
            )
        )
    if settings.cursor_cli_path:
        declarations.append((AgentType.CURSOR, {"cli_path": settings.cursor_cli_path}))
    return declarations


def _build_factory(agent_type: AgentType, config: dict) -> callable | None:
    """按 agent_type + config 构造 adapter factory。未配置/未实现返回 None。"""
    if agent_type == AgentType.OPENHANDS:
        if not config.get("url"):
            return None
        probe = OpenHandsAdapter()
        if not getattr(probe, "implemented", True):
            return None
        return lambda: OpenHandsAdapter()
    if agent_type == AgentType.CODEX:
        if not config.get("api_key"):
            return None
        base_url = config.get("base_url", "https://api.openai.com/v1")
        probe = CodexAdapter(api_key=config["api_key"], base_url=base_url)
        if not getattr(probe, "implemented", True):
            return None
        return lambda: CodexAdapter(api_key=config["api_key"], base_url=base_url)
    if agent_type == AgentType.CLAUDE_CODE:
        if not config.get("cli_path"):
            return None
        probe = ClaudeCodeAdapter(
            cli_path=config["cli_path"],
            work_dir=config.get("work_dir", ""),
            model=config.get("model", ""),
        )
        if not getattr(probe, "implemented", True):
            return None
        return lambda: ClaudeCodeAdapter(
            cli_path=config["cli_path"],
            work_dir=config.get("work_dir", ""),
            model=config.get("model", ""),
        )
    if agent_type == AgentType.CURSOR:
        if not config.get("cli_path"):
            return None
        probe = CursorAdapter(cli_path=config["cli_path"])
        if not getattr(probe, "implemented", True):
            return None
        return lambda: CursorAdapter(cli_path=config["cli_path"])
    return None


async def sync_registry_from_db(db, registry: AgentRegistry) -> None:
    """从 DB 同步 agent 声明到 registry (v6.8 W2.1 双读)。

    - DB 有 active 全局 agent 声明 → rebuild(DB 声明)
    - DB 空 → seed env 声明到 DB + reload(env 兜底)

    双读兼容: DB 优先, 空回退 env。name 须为合法 AgentType 值, 否则 skip + warn。
    """
    from arc.domain.capability.value_objects import (
        Capability,
        CapabilityScope,
        CapabilityStatus,
        CapabilityType,
    )
    from arc.infrastructure.repositories.capability import CapabilityRepository

    repo = CapabilityRepository(db)
    caps = await repo.list_capabilities(
        type=CapabilityType.AGENT, status=CapabilityStatus.ACTIVE, scope=CapabilityScope.GLOBAL
    )
    if not caps:
        for agent_type, config in env_agent_declarations():
            existing = await repo.get_by_name(agent_type.value)
            if not existing:
                await repo.create(
                    Capability(
                        id=uuid.uuid4(),
                        name=agent_type.value,
                        type=CapabilityType.AGENT,
                        config=config,
                        status=CapabilityStatus.ACTIVE,
                        scope=CapabilityScope.GLOBAL,
                    )
                )
        registry.reload()
        return

    declarations: list[tuple[AgentType, dict]] = []
    for cap in caps:
        try:
            agent_type = AgentType(cap.name)
        except ValueError:
            logger.warning("Skip unknown agent declaration name: %s", cap.name)
            continue
        declarations.append((agent_type, cap.config))
    registry.rebuild(declarations)


def create_agent_registry() -> AgentRegistry:
    """Build registry from settings (env 声明; 启动时 sync_registry_from_db 覆盖为 DB)。"""
    registry = AgentRegistry()
    registry.reload()
    return registry


agent_registry = create_agent_registry()
