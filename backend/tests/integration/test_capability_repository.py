"""CapabilityRepository 集成测试 (v6.8.0 W1).

真实 PG: create/get/get_by_name/list(过滤)/update/delete + skill config 持久化。
"""
from __future__ import annotations

import uuid
from dataclasses import replace

import pytest

from arc.domain.capability.value_objects import (
    Capability,
    CapabilityScope,
    CapabilityStatus,
    CapabilityType,
)


def _make_capability(
    *,
    name: str = "openhands",
    type: CapabilityType = CapabilityType.AGENT,
    status: CapabilityStatus = CapabilityStatus.ACTIVE,
    scope: CapabilityScope = CapabilityScope.GLOBAL,
    config: dict | None = None,
) -> Capability:
    return Capability(
        id=uuid.uuid4(),
        name=name,
        type=type,
        config=config or {"adapter": "openhands"},
        status=status,
        scope=scope,
    )


class TestCapabilityCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get(self, db_session, cleanup):
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        cap = _make_capability(
            name="openhands", config={"adapter": "openhands", "model": "gpt-4"}
        )
        created = await repo.create(cap)

        assert created.id == cap.id
        assert created.name == "openhands"
        assert created.type == CapabilityType.AGENT
        assert created.config["model"] == "gpt-4"
        assert created.is_active is True

        fetched = await repo.get_by_id(cap.id)
        assert fetched is not None
        assert fetched.name == "openhands"
        assert fetched.config == {"adapter": "openhands", "model": "gpt-4"}

    @pytest.mark.asyncio
    async def test_get_not_found(self, db_session, cleanup):
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        assert await repo.get_by_id(uuid.uuid4()) is None

    @pytest.mark.asyncio
    async def test_get_by_name(self, db_session, cleanup):
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        await repo.create(_make_capability(name="codex"))

        fetched = await repo.get_by_name("codex")
        assert fetched is not None
        assert fetched.name == "codex"
        assert await repo.get_by_name("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_with_filters(self, db_session, cleanup):
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        await repo.create(
            _make_capability(
                name="a1",
                type=CapabilityType.AGENT,
                status=CapabilityStatus.ACTIVE,
                scope=CapabilityScope.GLOBAL,
            )
        )
        await repo.create(
            _make_capability(
                name="s1",
                type=CapabilityType.SKILL,
                status=CapabilityStatus.ACTIVE,
                scope=CapabilityScope.PROJECT,
            )
        )
        await repo.create(
            _make_capability(
                name="a2",
                type=CapabilityType.AGENT,
                status=CapabilityStatus.DISABLED,
                scope=CapabilityScope.GLOBAL,
            )
        )

        # 按 type
        agents = await repo.list_capabilities(type=CapabilityType.AGENT)
        assert len(agents) == 2
        # 按 type + status
        active_agents = await repo.list_capabilities(
            type=CapabilityType.AGENT, status=CapabilityStatus.ACTIVE
        )
        assert len(active_agents) == 1
        assert active_agents[0].name == "a1"
        # 按 scope
        project_caps = await repo.list_capabilities(scope=CapabilityScope.PROJECT)
        assert len(project_caps) == 1
        assert project_caps[0].name == "s1"

    @pytest.mark.asyncio
    async def test_update(self, db_session, cleanup):
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        cap = _make_capability(name="old")
        await repo.create(cap)

        # 值对象不可变, 用 dataclasses.replace 创建变更实例
        updated_cap = replace(
            cap, name="new", status=CapabilityStatus.DISABLED, config={"x": 1}
        )
        result = await repo.update(updated_cap)

        assert result.name == "new"
        assert result.status == CapabilityStatus.DISABLED
        assert result.config == {"x": 1}

        fetched = await repo.get_by_id(cap.id)
        assert fetched is not None
        assert fetched.name == "new"
        assert fetched.is_active is False

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self, db_session, cleanup):
        from arc.domain.errors import NotFoundError
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        ghost = _make_capability(name="ghost")
        with pytest.raises(NotFoundError):
            await repo.update(ghost)

    @pytest.mark.asyncio
    async def test_delete(self, db_session, cleanup):
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        cap = _make_capability(name="to-delete")
        await repo.create(cap)

        assert await repo.delete(cap.id) is True
        assert await repo.get_by_id(cap.id) is None
        # 再删返回 False
        assert await repo.delete(cap.id) is False

    @pytest.mark.asyncio
    async def test_skill_capability_config(self, db_session, cleanup):
        """skill 类型能力 config 存 directory (W2 加载器读取)。"""
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        skill = _make_capability(
            name="ui-design",
            type=CapabilityType.SKILL,
            config={"directory": "/skills/ui-design"},
        )
        created = await repo.create(skill)
        fetched = await repo.get_by_id(created.id)

        assert fetched is not None
        assert fetched.is_skill is True
        assert fetched.config["directory"] == "/skills/ui-design"

    @pytest.mark.asyncio
    async def test_list_by_ids(self, db_session, cleanup):
        """按 id 批量取, 过滤不存在的 id (W3)。"""
        from arc.infrastructure.repositories.capability import CapabilityRepository

        repo = CapabilityRepository(db_session)
        c1 = await repo.create(_make_capability(name="c1"))
        c2 = await repo.create(_make_capability(name="c2"))
        await repo.create(_make_capability(name="c3"))

        # 混合存在 + 不存在的 id
        result = await repo.list_by_ids([c1.id, c2.id, uuid.uuid4()])
        assert len(result) == 2
        assert {c.name for c in result} == {"c1", "c2"}
        # 空列表
        assert await repo.list_by_ids([]) == []
