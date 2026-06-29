"""Skill 注入执行链集成测试 (v6.17 T7).

验证端到端: 配置 skill (含 tools) → TaskContextBuilder.build(phase) →
TaskContext 含 skill 规范 + tool_specs, to_markdown 输出技能规范段。
真实 DB (savepoint 隔离) + mock LLM (experience search 走 embed)。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

_TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def mock_llm():
    """Mock LLM adapter (experience search_similar 走 embed)。"""
    with patch("arc.application.ai.llm_adapter.create_llm_adapter") as factory:
        adapter = AsyncMock()
        adapter.chat = AsyncMock()
        adapter.embed = AsyncMock(return_value=[0.1] * 1536)
        adapter.close = AsyncMock()
        factory.return_value = adapter
        yield adapter


async def _setup_skill_phase(client: AsyncClient, db_session) -> tuple:
    """建 project + todo + skill(inline 含 tools) + 配 development 环节, 返回 todo。"""
    resp = await client.post("/api/projects", json={"name": "skill注入测试"})
    assert resp.status_code in (200, 201)
    project_id = uuid.UUID(resp.json()["id"])

    from arc.domain.capability.value_objects import (
        Capability,
        CapabilityScope,
        CapabilityStatus,
        CapabilityType,
    )
    from arc.domain.todo.entity import Todo
    from arc.infrastructure.repositories.capability import CapabilityRepository
    from arc.infrastructure.repositories.project import ProjectRepository
    from arc.infrastructure.repositories.todo import TodoRepository

    skill = await CapabilityRepository(db_session).create(
        Capability(
            id=uuid.uuid4(),
            name="dev-skill",
            type=CapabilityType.SKILL,
            config={
                "source": "inline",
                "content": (
                    "---\nname: dev-skill\ndescription: 开发规范\n"
                    "tools:\n  - name: search_docs\n    description: 搜索文档\n"
                    "    parameters: {type: object}\n---\n遵循 TDD\n"
                ),
            },
            status=CapabilityStatus.ACTIVE,
            scope=CapabilityScope.GLOBAL,
        )
    )

    project = await ProjectRepository(db_session).get_by_id(project_id)
    assert project is not None
    project.update_phase_capabilities("development", [str(skill.id)])
    await ProjectRepository(db_session).update(project)

    todo = await TodoRepository(db_session).create(
        Todo(title="dev任务", project_id=project_id), user_id=_TEST_USER_ID,
    )
    await db_session.commit()
    return todo


class TestSkillInjectionIntegration:
    @pytest.mark.asyncio
    async def test_skill_injected_into_agent_context(
        self, client: AsyncClient, db_session, mock_llm
    ) -> None:
        todo = await _setup_skill_phase(client, db_session)

        from arc.application.agent.context_builder import TaskContextBuilder

        ctx = await TaskContextBuilder(db_session).build(todo.id, "development")

        # skill 规范文本注入
        assert len(ctx.skill_specs) == 1
        assert "dev-skill" in ctx.skill_specs[0]
        # inline 工具集注入
        assert len(ctx.tool_specs) == 1
        assert ctx.tool_specs[0].name == "search_docs"
        assert ctx.tool_specs[0].is_inline
        assert ctx.tool_specs[0].parameters == {"type": "object"}

        # to_markdown 含技能规范段 + 工具指引
        md = ctx.to_markdown()
        assert "## 本环节技能规范" in md
        assert "## 本环节启用工具" in md
        assert "search_docs" in md

    @pytest.mark.asyncio
    async def test_no_phase_no_skill_injected(
        self, client: AsyncClient, db_session, mock_llm
    ) -> None:
        """不传 phase_type → 不注入 skill (向后兼容)。"""
        resp = await client.post("/api/projects", json={"name": "无skill测试"})
        project_id = uuid.UUID(resp.json()["id"])

        from arc.domain.todo.entity import Todo
        from arc.infrastructure.repositories.todo import TodoRepository

        todo = await TodoRepository(db_session).create(
            Todo(title="t", project_id=project_id), user_id=_TEST_USER_ID,
        )
        await db_session.commit()

        from arc.application.agent.context_builder import TaskContextBuilder

        ctx = await TaskContextBuilder(db_session).build(todo.id, None)
        assert ctx.skill_specs == []
        assert ctx.tool_specs == []
        assert "本环节技能规范" not in ctx.to_markdown()

    @pytest.mark.asyncio
    async def test_phase_without_skill_config(
        self, client: AsyncClient, db_session, mock_llm
    ) -> None:
        """传 phase 但环节未配 skill → 不注入 (graceful)。"""
        resp = await client.post("/api/projects", json={"name": "空环节测试"})
        project_id = uuid.UUID(resp.json()["id"])

        from arc.domain.todo.entity import Todo
        from arc.infrastructure.repositories.todo import TodoRepository

        todo = await TodoRepository(db_session).create(
            Todo(title="t2", project_id=project_id), user_id=_TEST_USER_ID,
        )
        await db_session.commit()

        from arc.application.agent.context_builder import TaskContextBuilder

        ctx = await TaskContextBuilder(db_session).build(todo.id, "development")
        assert ctx.skill_specs == []
        assert ctx.tool_specs == []
