from __future__ import annotations

import uuid

import pytest

from arc.domain.experience.entity import Experience
from arc.domain.todo.value_objects import Tag

# ---------------------------------------------------------------------------
# Entity creation
# ---------------------------------------------------------------------------

class TestExperienceCreation:
    def test_create_with_required_fields(self) -> None:
        exp = Experience(title="Auth pattern", problem="JWT refresh", solution="Use sliding window")
        assert exp.title == "Auth pattern"
        assert exp.problem == "JWT refresh"
        assert exp.solution == "Use sliding window"
        assert isinstance(exp.id, uuid.UUID)
        assert exp.todo_id is None
        assert exp.confidence == 0.0
        assert exp.reuse_count == 0
        assert exp.embedding is None
        assert exp.decisions == []
        assert exp.pitfalls == []

    def test_create_with_all_fields(self) -> None:
        todo_id = uuid.uuid4()
        tag = Tag(label="auth", color="#00ff00")
        exp = Experience(
            title="Auth pattern",
            problem="JWT refresh",
            solution="Sliding window",
            todo_id=todo_id,
            decisions=["Use RS256", "15min expiry"],
            pitfalls=["Don't store in localStorage"],
            applicable_scenarios="Any web app with JWT",
            tags=[tag],
            embedding=[0.1, 0.2, 0.3],
            confidence=0.85,
            metadata={"source": "manual"},
        )
        assert exp.todo_id == todo_id
        assert exp.decisions == ["Use RS256", "15min expiry"]
        assert exp.pitfalls == ["Don't store in localStorage"]
        assert exp.tags == [tag]
        assert exp.embedding == [0.1, 0.2, 0.3]
        assert exp.confidence == 0.85
        assert exp.metadata == {"source": "manual"}


# ---------------------------------------------------------------------------
# increment_reuse
# ---------------------------------------------------------------------------

class TestIncrementReuse:
    def test_increments_by_one(self) -> None:
        exp = Experience(title="t", problem="p", solution="s")
        assert exp.reuse_count == 0
        exp.increment_reuse()
        assert exp.reuse_count == 1

    def test_increments_multiple_times(self) -> None:
        exp = Experience(title="t", problem="p", solution="s")
        for _ in range(5):
            exp.increment_reuse()
        assert exp.reuse_count == 5

    def test_increment_updates_timestamp(self) -> None:
        exp = Experience(title="t", problem="p", solution="s")
        original = exp.updated_at
        exp.increment_reuse()
        assert exp.updated_at >= original


# ---------------------------------------------------------------------------
# update_confidence
# ---------------------------------------------------------------------------

class TestUpdateConfidence:
    def test_update_valid_confidence(self) -> None:
        exp = Experience(title="t", problem="p", solution="s")
        exp.update_confidence(0.75)
        assert exp.confidence == 0.75

    def test_update_to_zero(self) -> None:
        exp = Experience(title="t", problem="p", solution="s", confidence=0.5)
        exp.update_confidence(0.0)
        assert exp.confidence == 0.0

    def test_update_to_one(self) -> None:
        exp = Experience(title="t", problem="p", solution="s")
        exp.update_confidence(1.0)
        assert exp.confidence == 1.0

    def test_update_updates_timestamp(self) -> None:
        exp = Experience(title="t", problem="p", solution="s")
        original = exp.updated_at
        exp.update_confidence(0.5)
        assert exp.updated_at >= original

    def test_reject_negative_confidence(self) -> None:
        exp = Experience(title="t", problem="p", solution="s")
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            exp.update_confidence(-0.1)

    def test_reject_above_one_confidence(self) -> None:
        exp = Experience(title="t", problem="p", solution="s")
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            exp.update_confidence(1.01)

    def test_reject_far_out_of_range(self) -> None:
        exp = Experience(title="t", problem="p", solution="s")
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            exp.update_confidence(5.0)
