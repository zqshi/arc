"""Tests for domain/orchestration entities."""

import uuid

import pytest

from arc.domain.orchestration.entity import OrchestrationPlan, Subtask
from arc.domain.orchestration.value_objects import SubtaskType, WorkerRole, WorkerStatus


class TestSubtask:
    def test_creation_defaults(self):
        st = Subtask(description="analyze", task_type=SubtaskType.READ_ANALYSIS, worker_role=WorkerRole.EXPLORER)
        assert st.status == WorkerStatus.PENDING
        assert st.result == ""
        assert st.tokens_used == 0

    def test_start(self):
        st = Subtask(description="x", task_type=SubtaskType.CODE_SEARCH, worker_role=WorkerRole.EXPLORER)
        st.start()
        assert st.status == WorkerStatus.RUNNING

    def test_complete(self):
        st = Subtask(description="x", task_type=SubtaskType.FILE_WRITE, worker_role=WorkerRole.WRITER)
        st.complete("done", tokens=500, elapsed_ms=1200)
        assert st.status == WorkerStatus.COMPLETED
        assert st.result == "done"
        assert st.tokens_used == 500
        assert st.elapsed_ms == 1200

    def test_fail(self):
        st = Subtask(description="x", task_type=SubtaskType.COMMAND_EXEC, worker_role=WorkerRole.WRITER)
        st.fail("timeout")
        assert st.status == WorkerStatus.ERROR
        assert st.result == "timeout"


class TestOrchestrationPlan:
    def test_add_subtask(self):
        plan = OrchestrationPlan(conversation_id=uuid.uuid4(), parent_message_id="msg-1")
        st = plan.add_subtask("read file", SubtaskType.READ_ANALYSIS, WorkerRole.EXPLORER)
        assert len(plan.subtasks) == 1
        assert st.description == "read file"

    def test_execution_layers_no_deps(self):
        plan = OrchestrationPlan(conversation_id=uuid.uuid4(), parent_message_id="msg-1")
        plan.add_subtask("a", SubtaskType.READ_ANALYSIS, WorkerRole.EXPLORER)
        plan.add_subtask("b", SubtaskType.CODE_SEARCH, WorkerRole.EXPLORER)
        layers = plan.execution_layers()
        assert len(layers) == 1
        assert len(layers[0]) == 2

    def test_execution_layers_with_deps(self):
        plan = OrchestrationPlan(conversation_id=uuid.uuid4(), parent_message_id="msg-1")
        st1 = plan.add_subtask("read", SubtaskType.READ_ANALYSIS, WorkerRole.EXPLORER)
        plan.add_subtask("write", SubtaskType.FILE_WRITE, WorkerRole.WRITER, depends_on=[st1.id])
        layers = plan.execution_layers()
        assert len(layers) == 2
        assert layers[0][0].description == "read"
        assert layers[1][0].description == "write"

    def test_is_complete(self):
        plan = OrchestrationPlan(conversation_id=uuid.uuid4(), parent_message_id="msg-1")
        st = plan.add_subtask("x", SubtaskType.SYNTHESIS, WorkerRole.SYNTHESIZER)
        assert not plan.is_complete
        st.complete("ok")
        assert plan.is_complete

    def test_total_tokens(self):
        plan = OrchestrationPlan(conversation_id=uuid.uuid4(), parent_message_id="msg-1")
        s1 = plan.add_subtask("a", SubtaskType.READ_ANALYSIS, WorkerRole.EXPLORER)
        s2 = plan.add_subtask("b", SubtaskType.CODE_SEARCH, WorkerRole.EXPLORER)
        s1.complete("ok", tokens=100)
        s2.complete("ok", tokens=200)
        assert plan.total_tokens == 300

    def test_mark_complete(self):
        plan = OrchestrationPlan(conversation_id=uuid.uuid4(), parent_message_id="msg-1")
        assert plan.completed_at is None
        plan.mark_complete()
        assert plan.status == WorkerStatus.COMPLETED
        assert plan.completed_at is not None

    def test_circular_deps_fallback(self):
        plan = OrchestrationPlan(conversation_id=uuid.uuid4(), parent_message_id="msg-1")
        s1 = plan.add_subtask("a", SubtaskType.READ_ANALYSIS, WorkerRole.EXPLORER, depends_on=[uuid.uuid4()])
        s2 = plan.add_subtask("b", SubtaskType.READ_ANALYSIS, WorkerRole.EXPLORER, depends_on=[s1.id])
        # s1 depends on nonexistent → can't resolve, forced into single layer
        layers = plan.execution_layers()
        assert len(layers) >= 1
