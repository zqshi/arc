from __future__ import annotations

import uuid

import pytest

from arc.domain.pipeline.value_objects import PhaseType
from arc.domain.todo.entity import InvalidStatusTransition, Todo
from arc.domain.todo.value_objects import Tag, TodoStatus


class TestTodoCreation:
    def test_create_with_defaults(self) -> None:
        todo = Todo(title="Implement login")
        assert todo.title == "Implement login"
        assert todo.description == ""
        assert todo.status == TodoStatus.PENDING
        assert isinstance(todo.id, uuid.UUID)
        assert todo.tags == []
        assert todo.current_phase is None
        assert todo.error_reason == ""

    def test_create_with_all_fields(self) -> None:
        tag = Tag(label="backend", color="#ff0000")
        todo = Todo(
            title="Build API",
            description="REST endpoints",
            tags=[tag],
        )
        assert todo.description == "REST endpoints"
        assert todo.tags == [tag]


class TestTodoPipelineTransitions:
    def test_start_pipeline(self) -> None:
        todo = Todo(title="t")
        todo.start_pipeline()
        assert todo.status == TodoStatus.ACTIVE
        assert todo.current_phase == PhaseType.CLARIFICATION

    def test_update_phase(self) -> None:
        todo = Todo(title="t")
        todo.start_pipeline()
        todo.update_phase(PhaseType.UI_DESIGN)
        assert todo.current_phase == PhaseType.UI_DESIGN

    def test_update_phase_requires_active(self) -> None:
        todo = Todo(title="t")
        with pytest.raises(InvalidStatusTransition):
            todo.update_phase(PhaseType.CLARIFICATION)

    def test_complete(self) -> None:
        todo = Todo(title="t")
        todo.start_pipeline()
        todo.complete()
        assert todo.status == TodoStatus.DONE

    def test_full_lifecycle(self) -> None:
        todo = Todo(title="Full lifecycle")
        assert todo.status == TodoStatus.PENDING
        todo.start_pipeline()
        assert todo.status == TodoStatus.ACTIVE
        assert todo.current_phase == PhaseType.CLARIFICATION
        todo.update_phase(PhaseType.DEVELOPMENT)
        assert todo.current_phase == PhaseType.DEVELOPMENT
        todo.complete()
        assert todo.status == TodoStatus.DONE


class TestTodoErrorTransitions:
    def test_mark_error_from_pending(self) -> None:
        todo = Todo(title="t")
        todo.mark_error("something broke")
        assert todo.status == TodoStatus.ERROR
        assert todo.error_reason == "something broke"

    def test_mark_error_from_active(self) -> None:
        todo = Todo(title="t")
        todo.start_pipeline()
        todo.mark_error("AI timeout")
        assert todo.status == TodoStatus.ERROR

    def test_cannot_mark_error_from_done(self) -> None:
        todo = Todo(title="t")
        todo.start_pipeline()
        todo.complete()
        with pytest.raises(InvalidStatusTransition):
            todo.mark_error("oops")

    def test_retry_from_error(self) -> None:
        todo = Todo(title="t")
        todo.mark_error("fail")
        todo.retry()
        assert todo.status == TodoStatus.PENDING
        assert todo.current_phase is None

    def test_mark_error_requires_reason(self) -> None:
        todo = Todo(title="t")
        with pytest.raises(ValueError, match="reason is required"):
            todo.mark_error("")
        with pytest.raises(ValueError, match="reason is required"):
            todo.mark_error("   ")


class TestTodoInvalidTransitions:
    def test_pending_cannot_complete(self) -> None:
        todo = Todo(title="t")
        with pytest.raises(InvalidStatusTransition):
            todo.complete()

    def test_done_cannot_transition(self) -> None:
        todo = Todo(title="t")
        todo.start_pipeline()
        todo.complete()
        with pytest.raises(InvalidStatusTransition):
            todo.start_pipeline()


class TestTodoTimestamps:
    def test_updated_at_changes_on_transition(self) -> None:
        todo = Todo(title="t")
        original = todo.updated_at
        todo.start_pipeline()
        assert todo.updated_at >= original
