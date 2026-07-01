"""AgentRegistry DB sync 集成测试 (v6.8.0 W2.1).

真实 PG: sync_registry_from_db 双读 (DB 空→seed env+reload, DB 非空→rebuild from DB)。
"""
from __future__ import annotations

import uuid

import pytest

from arc.application.agent.registry import AgentRegistry, sync_registry_from_db
from arc.domain.agent.value_objects import AgentType
from arc.domain.capability.value_objects import (
    Capability,
    CapabilityScope,
    CapabilityStatus,
    CapabilityType,
)


def _only_openhands_env(monkeypatch):
    from arc.config import settings

    monkeypatch.setattr(settings, "openhands_url", "http://x:3000")
    monkeypatch.setattr(settings, "openhands_api_key", "")
    monkeypatch.setattr(settings, "codex_api_key", "")
    monkeypatch.setattr(settings, "claude_code_path", "")
    monkeypatch.setattr(settings, "cursor_cli_path", "")


class TestSyncRegistryFromDb:
    @pytest.mark.asyncio
    async def test_db_empty_seeds_env(self, db_session, cleanup, monkeypatch):
        _only_openhands_env(monkeypatch)

        registry = AgentRegistry()
        await sync_registry_from_db(db_session, registry)

        assert AgentType.OPENHANDS in registry.available_agents()
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        caps = await repo.list_capabilities(type=CapabilityType.AGENT)
        assert "openhands" in [c.name for c in caps]

    @pytest.mark.asyncio
    async def test_seed_idempotent(self, db_session, cleanup, monkeypatch):
        _only_openhands_env(monkeypatch)

        await sync_registry_from_db(db_session, AgentRegistry())
        # 第二次: DB 非空 → rebuild from DB, 不重复 seed
        await sync_registry_from_db(db_session, AgentRegistry())

        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        caps = await repo.list_capabilities(type=CapabilityType.AGENT)
        openhands = [c for c in caps if c.name == "openhands"]
        assert len(openhands) == 1  # 幂等

    @pytest.mark.asyncio
    async def test_db_declarations_override_env(self, db_session, cleanup, monkeypatch):
        _only_openhands_env(monkeypatch)  # env 有 openhands

        # DB 只有 codex 声明
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        await repo.create(
            Capability(
                id=uuid.uuid4(),
                name="codex",
                type=CapabilityType.AGENT,
                config={"api_key": "k", "base_url": "x"},
                status=CapabilityStatus.ACTIVE,
                scope=CapabilityScope.GLOBAL,
            )
        )

        registry = AgentRegistry()
        await sync_registry_from_db(db_session, registry)

        # DB 优先: 只有 codex, env openhands 被覆盖
        assert AgentType.CODEX in registry.available_agents()
        assert AgentType.OPENHANDS not in registry.available_agents()
