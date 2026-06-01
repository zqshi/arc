"""Tests for domain/orchestration value objects."""

from arc.domain.orchestration.value_objects import (
    SubtaskType,
    WorkerRole,
    WorkerStatus,
)


class TestWorkerRole:
    def test_enum_values(self):
        assert WorkerRole.ORCHESTRATOR == "orchestrator"
        assert WorkerRole.EXPLORER == "explorer"
        assert WorkerRole.WRITER == "writer"
        assert WorkerRole.SYNTHESIZER == "synthesizer"

    def test_enum_completeness(self):
        expected = {"orchestrator", "explorer", "writer", "synthesizer"}
        assert {r.value for r in WorkerRole} == expected

    def test_equality_same_value(self):
        assert WorkerRole.ORCHESTRATOR == WorkerRole("orchestrator")

    def test_equality_string_coercion(self):
        assert WorkerRole.EXPLORER == "explorer"

    def test_invalid_value_raises(self):
        try:
            WorkerRole("nonexistent")
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestSubtaskType:
    def test_enum_values(self):
        assert SubtaskType.READ_ANALYSIS == "read_analysis"
        assert SubtaskType.CODE_SEARCH == "code_search"
        assert SubtaskType.FILE_WRITE == "file_write"
        assert SubtaskType.COMMAND_EXEC == "command_exec"
        assert SubtaskType.SYNTHESIS == "synthesis"

    def test_enum_completeness(self):
        expected = {"read_analysis", "code_search", "file_write", "command_exec", "synthesis"}
        assert {t.value for t in SubtaskType} == expected

    def test_equality_same_value(self):
        assert SubtaskType.FILE_WRITE == SubtaskType("file_write")

    def test_equality_string_coercion(self):
        assert SubtaskType.SYNTHESIS == "synthesis"

    def test_invalid_value_raises(self):
        try:
            SubtaskType("nonexistent")
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestWorkerStatus:
    def test_enum_values(self):
        assert WorkerStatus.PENDING == "pending"
        assert WorkerStatus.RUNNING == "running"
        assert WorkerStatus.COMPLETED == "completed"
        assert WorkerStatus.ERROR == "error"
        assert WorkerStatus.CANCELLED == "cancelled"

    def test_enum_completeness(self):
        expected = {"pending", "running", "completed", "error", "cancelled"}
        assert {s.value for s in WorkerStatus} == expected

    def test_equality_same_value(self):
        assert WorkerStatus.COMPLETED == WorkerStatus("completed")

    def test_equality_string_coercion(self):
        assert WorkerStatus.ERROR == "error"

    def test_invalid_value_raises(self):
        try:
            WorkerStatus("nonexistent")
            assert False, "Should raise ValueError"
        except ValueError:
            pass

    def test_terminal_states_semantics(self):
        """COMPLETED, ERROR, CANCELLED are terminal states."""
        terminal = {WorkerStatus.COMPLETED, WorkerStatus.ERROR, WorkerStatus.CANCELLED}
        non_terminal = {WorkerStatus.PENDING, WorkerStatus.RUNNING}
        assert terminal | non_terminal == set(WorkerStatus)
