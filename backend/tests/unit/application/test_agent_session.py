from __future__ import annotations

import pytest

from arc.application.agent.context_builder import TaskContext
from arc.application.agent.events import AgentEvent, EventType
from arc.application.agent.registry import AgentRegistry
from arc.domain.agent.value_objects import AgentType


class TestTaskContext:
    def test_to_dict_roundtrip(self) -> None:
        ctx = TaskContext(
            todo_id="abc-123",
            todo_title="Build login",
            todo_description="OAuth login page",
            requirement_spec={"summary": "login needed"},
        )
        d = ctx.to_dict()
        assert d["todo_title"] == "Build login"
        assert d["requirement_spec"] == {"summary": "login needed"}
        assert d["ui_design"] == {}

    def test_to_markdown_includes_sections(self) -> None:
        ctx = TaskContext(
            todo_id="abc-123",
            todo_title="Build login",
            todo_description="OAuth login page",
            requirement_spec={"summary": "needs OAuth"},
            tech_architecture={"stack": "FastAPI"},
        )
        md = ctx.to_markdown()
        assert "Build login" in md
        assert "需求规格" in md
        assert "技术架构" in md

    def test_empty_context(self) -> None:
        ctx = TaskContext(todo_id="t-1", todo_title="Test", todo_description="")
        md = ctx.to_markdown()
        assert "Test" in md


class TestAgentEvent:
    def test_event_creation(self) -> None:
        event = AgentEvent(
            event_id="evt-1",
            event_type=EventType.LOG,
            content="hello",
        )
        assert event.event_id == "evt-1"
        assert event.event_type == EventType.LOG

    def test_event_with_metadata(self) -> None:
        event = AgentEvent(
            event_id="evt-2",
            event_type=EventType.ACTION,
            content="run test",
            metadata={"tool": "pytest"},
        )
        assert event.metadata["tool"] == "pytest"


class TestAgentRegistry:
    def test_register_and_create(self) -> None:
        registry = AgentRegistry()

        class FakeAdapter:
            agent_type = AgentType.OPENHANDS

        registry.register(AgentType.OPENHANDS, FakeAdapter)
        adapter = registry.create(AgentType.OPENHANDS)
        assert adapter.agent_type == AgentType.OPENHANDS

    def test_available_agents(self) -> None:
        registry = AgentRegistry()
        assert registry.available_agents() == []
        registry.register(AgentType.CODEX, lambda: None)
        assert AgentType.CODEX in registry.available_agents()

    def test_is_available(self) -> None:
        registry = AgentRegistry()
        assert not registry.is_available(AgentType.CURSOR)
        registry.register(AgentType.CURSOR, lambda: None)
        assert registry.is_available(AgentType.CURSOR)

    def test_create_unregistered_raises(self) -> None:
        registry = AgentRegistry()
        with pytest.raises(ValueError, match="not available"):
            registry.create(AgentType.CLAUDE_CODE)
