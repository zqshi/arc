"""Tests for domain/todo value objects."""

import pytest

from arc.domain.todo.value_objects import (
    VALID_TRANSITIONS,
    ConversationPurpose,
    ExperienceCategory,
    ExperienceScope,
    ExperienceSource,
    ExperienceStatus,
    MessageRole,
    Tag,
    TodoStatus,
)


class TestTodoStatus:
    def test_enum_values_complete(self):
        expected = {"pending", "active", "suspended", "done", "error", "abandoned"}
        assert {ts.value for ts in TodoStatus} == expected

    def test_enum_count(self):
        assert len(TodoStatus) == 6

    def test_str_equality(self):
        assert TodoStatus.PENDING == "pending"
        assert TodoStatus.ACTIVE == "active"
        assert TodoStatus.SUSPENDED == "suspended"
        assert TodoStatus.DONE == "done"
        assert TodoStatus.ERROR == "error"
        assert TodoStatus.ABANDONED == "abandoned"

    def test_from_value(self):
        assert TodoStatus("done") == TodoStatus.DONE


class TestValidTransitions:
    def test_all_statuses_have_transitions(self):
        for ts in TodoStatus:
            assert ts in VALID_TRANSITIONS

    def test_pending_can_go_to_active_error_abandoned(self):
        assert VALID_TRANSITIONS[TodoStatus.PENDING] == {
            TodoStatus.ACTIVE,
            TodoStatus.ERROR,
            TodoStatus.ABANDONED,
        }

    def test_active_can_go_to_done_error_abandoned(self):
        assert VALID_TRANSITIONS[TodoStatus.ACTIVE] == {
            TodoStatus.DONE,
            TodoStatus.ERROR,
            TodoStatus.ABANDONED,
            TodoStatus.SUSPENDED,
        }

    def test_done_is_terminal(self):
        assert VALID_TRANSITIONS[TodoStatus.DONE] == set()

    def test_error_can_go_back_to_pending(self):
        assert VALID_TRANSITIONS[TodoStatus.ERROR] == {TodoStatus.PENDING}

    def test_abandoned_is_terminal(self):
        assert VALID_TRANSITIONS[TodoStatus.ABANDONED] == set()

    def test_no_transition_to_self(self):
        for status, targets in VALID_TRANSITIONS.items():
            assert status not in targets


class TestConversationPurpose:
    def test_enum_values_complete(self):
        expected = {
            "clarification",
            "ui_design",
            "architecture",
            "development",
            "testing",
            "deployment",
            "review",
            "unified",
            "planning",
        }
        assert {cp.value for cp in ConversationPurpose} == expected

    def test_enum_count(self):
        assert len(ConversationPurpose) == 9

    def test_str_equality(self):
        assert ConversationPurpose.UNIFIED == "unified"
        assert ConversationPurpose.PLANNING == "planning"

    def test_from_value(self):
        assert ConversationPurpose("review") == ConversationPurpose.REVIEW


class TestMessageRole:
    def test_enum_values_complete(self):
        expected = {"user", "assistant", "system"}
        assert {mr.value for mr in MessageRole} == expected

    def test_enum_count(self):
        assert len(MessageRole) == 3

    def test_str_equality(self):
        assert MessageRole.USER == "user"
        assert MessageRole.ASSISTANT == "assistant"
        assert MessageRole.SYSTEM == "system"

    def test_from_value(self):
        assert MessageRole("system") == MessageRole.SYSTEM


class TestExperienceScope:
    def test_enum_values_complete(self):
        expected = {"personal", "project"}
        assert {es.value for es in ExperienceScope} == expected

    def test_enum_count(self):
        assert len(ExperienceScope) == 2

    def test_str_equality(self):
        assert ExperienceScope.PERSONAL == "personal"
        assert ExperienceScope.PROJECT == "project"


class TestExperienceStatus:
    def test_enum_values_complete(self):
        expected = {"draft", "confirmed", "archived"}
        assert {es.value for es in ExperienceStatus} == expected

    def test_enum_count(self):
        assert len(ExperienceStatus) == 3

    def test_str_equality(self):
        assert ExperienceStatus.DRAFT == "draft"
        assert ExperienceStatus.CONFIRMED == "confirmed"
        assert ExperienceStatus.ARCHIVED == "archived"


class TestExperienceCategory:
    def test_enum_values_complete(self):
        expected = {
            "technical",
            "business_rule",
            "pitfall",
            "architecture_decision",
            "scope_change",
            "estimation",
        }
        assert {ec.value for ec in ExperienceCategory} == expected

    def test_enum_count(self):
        assert len(ExperienceCategory) == 6

    def test_str_equality(self):
        assert ExperienceCategory.TECHNICAL == "technical"
        assert ExperienceCategory.PITFALL == "pitfall"

    def test_from_value(self):
        assert ExperienceCategory("estimation") == ExperienceCategory.ESTIMATION


class TestExperienceSource:
    def test_enum_values_complete(self):
        expected = {
            "todo_completion",
            "scope_change",
            "version_release",
            "manual",
        }
        assert {es.value for es in ExperienceSource} == expected

    def test_enum_count(self):
        assert len(ExperienceSource) == 4

    def test_str_equality(self):
        assert ExperienceSource.TODO_COMPLETION == "todo_completion"
        assert ExperienceSource.MANUAL == "manual"

    def test_from_value(self):
        assert ExperienceSource("manual") == ExperienceSource.MANUAL


class TestTag:
    def test_create_with_values(self):
        tag = Tag(label="bug", color="#ff0000")
        assert tag.label == "bug"
        assert tag.color == "#ff0000"

    def test_equality_same_values(self):
        tag1 = Tag(label="feature", color="#00ff00")
        tag2 = Tag(label="feature", color="#00ff00")
        assert tag1 == tag2

    def test_inequality_different_label(self):
        tag1 = Tag(label="bug", color="#ff0000")
        tag2 = Tag(label="feature", color="#ff0000")
        assert tag1 != tag2

    def test_inequality_different_color(self):
        tag1 = Tag(label="bug", color="#ff0000")
        tag2 = Tag(label="bug", color="#00ff00")
        assert tag1 != tag2

    def test_frozen_cannot_modify_label(self):
        tag = Tag(label="bug", color="#ff0000")
        with pytest.raises(Exception):
            tag.label = "feature"  # type: ignore

    def test_frozen_cannot_modify_color(self):
        tag = Tag(label="bug", color="#ff0000")
        with pytest.raises(Exception):
            tag.color = "#00ff00"  # type: ignore

    def test_hash_same_values(self):
        tag1 = Tag(label="bug", color="#ff0000")
        tag2 = Tag(label="bug", color="#ff0000")
        assert hash(tag1) == hash(tag2)

    def test_hash_different_values(self):
        tag1 = Tag(label="bug", color="#ff0000")
        tag2 = Tag(label="feature", color="#00ff00")
        assert hash(tag1) != hash(tag2)

    def test_usable_in_set(self):
        tag1 = Tag(label="bug", color="#ff0000")
        tag2 = Tag(label="bug", color="#ff0000")
        tag3 = Tag(label="feature", color="#00ff00")
        s = {tag1, tag2, tag3}
        assert len(s) == 2

    def test_usable_as_dict_key(self):
        tag = Tag(label="bug", color="#ff0000")
        d = {tag: "value"}
        assert d[Tag(label="bug", color="#ff0000")] == "value"

    def test_empty_strings_allowed(self):
        tag = Tag(label="", color="")
        assert tag.label == ""
        assert tag.color == ""
