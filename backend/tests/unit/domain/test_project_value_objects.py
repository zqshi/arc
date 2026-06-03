"""Tests for domain/project value objects."""

import pytest

from arc.domain.project.value_objects import (
    DEFAULT_CONVERSATION_CONFIG,
    DEFAULT_PIPELINE_CONFIG,
    VALID_VERSION_TRANSITIONS,
    AgentAutonomy,
    ExecutionMode,
    GateStrictness,
    ProjectStatus,
    VersionStatus,
)


class TestProjectStatus:
    def test_enum_values_complete(self):
        expected = {"active", "archived", "deleted"}
        assert {ps.value for ps in ProjectStatus} == expected

    def test_enum_count(self):
        assert len(ProjectStatus) == 3

    def test_str_equality(self):
        assert ProjectStatus.ACTIVE == "active"
        assert ProjectStatus.ARCHIVED == "archived"
        assert ProjectStatus.DELETED == "deleted"

    def test_identity_equality(self):
        assert ProjectStatus.ACTIVE == ProjectStatus.ACTIVE

    def test_from_value(self):
        assert ProjectStatus("archived") == ProjectStatus.ARCHIVED


class TestExecutionMode:
    def test_enum_values_complete(self):
        expected = {"pipeline", "conversation"}
        assert {em.value for em in ExecutionMode} == expected

    def test_enum_count(self):
        assert len(ExecutionMode) == 2

    def test_str_equality(self):
        assert ExecutionMode.PIPELINE == "pipeline"
        assert ExecutionMode.CONVERSATION == "conversation"

    def test_from_value(self):
        assert ExecutionMode("pipeline") == ExecutionMode.PIPELINE


class TestGateStrictness:
    def test_enum_values_complete(self):
        expected = {"strict", "moderate", "relaxed"}
        assert {gs.value for gs in GateStrictness} == expected

    def test_enum_count(self):
        assert len(GateStrictness) == 3

    def test_str_equality(self):
        assert GateStrictness.STRICT == "strict"
        assert GateStrictness.MODERATE == "moderate"
        assert GateStrictness.RELAXED == "relaxed"

    def test_from_value(self):
        assert GateStrictness("relaxed") == GateStrictness.RELAXED


class TestAgentAutonomy:
    def test_enum_values_complete(self):
        expected = {"full", "supervised"}
        assert {aa.value for aa in AgentAutonomy} == expected

    def test_enum_count(self):
        assert len(AgentAutonomy) == 2

    def test_str_equality(self):
        assert AgentAutonomy.FULL == "full"
        assert AgentAutonomy.SUPERVISED == "supervised"

    def test_from_value(self):
        assert AgentAutonomy("supervised") == AgentAutonomy.SUPERVISED


class TestVersionStatus:
    def test_enum_values_complete(self):
        expected = {"planning", "active", "released"}
        assert {vs.value for vs in VersionStatus} == expected

    def test_enum_count(self):
        assert len(VersionStatus) == 3

    def test_str_equality(self):
        assert VersionStatus.PLANNING == "planning"
        assert VersionStatus.ACTIVE == "active"
        assert VersionStatus.RELEASED == "released"

    def test_from_value(self):
        assert VersionStatus("active") == VersionStatus.ACTIVE


class TestValidVersionTransitions:
    def test_all_statuses_have_transitions(self):
        for vs in VersionStatus:
            assert vs in VALID_VERSION_TRANSITIONS

    def test_planning_can_go_to_active(self):
        assert VALID_VERSION_TRANSITIONS[VersionStatus.PLANNING] == {
            VersionStatus.ACTIVE,
        }

    def test_active_can_go_to_released_or_planning(self):
        assert VALID_VERSION_TRANSITIONS[VersionStatus.ACTIVE] == {
            VersionStatus.RELEASED,
            VersionStatus.PLANNING,
        }

    def test_released_is_terminal(self):
        assert VALID_VERSION_TRANSITIONS[VersionStatus.RELEASED] == set()

    def test_no_transition_to_self(self):
        for status, targets in VALID_VERSION_TRANSITIONS.items():
            assert status not in targets

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            VersionStatus("nonexistent")


class TestDefaultPipelineConfig:
    def test_has_enabled_phases(self):
        assert "enabled_phases" in DEFAULT_PIPELINE_CONFIG
        assert len(DEFAULT_PIPELINE_CONFIG["enabled_phases"]) == 7

    def test_has_required_phases(self):
        assert "required_phases" in DEFAULT_PIPELINE_CONFIG
        assert len(DEFAULT_PIPELINE_CONFIG["required_phases"]) == len(DEFAULT_PIPELINE_CONFIG["enabled_phases"])

    def test_required_phases_subset_of_enabled(self):
        enabled = set(DEFAULT_PIPELINE_CONFIG["enabled_phases"])
        required = set(DEFAULT_PIPELINE_CONFIG["required_phases"])
        assert required.issubset(enabled)

    def test_gate_strictness_is_strict(self):
        assert DEFAULT_PIPELINE_CONFIG["gate_strictness"] == "strict"

    def test_auto_advance_disabled(self):
        assert DEFAULT_PIPELINE_CONFIG["auto_advance"] is False

    def test_enabled_phases_match_phase_type_values(self):
        from arc.domain.pipeline.value_objects import PhaseType

        expected = {pt.value for pt in PhaseType}
        actual = set(DEFAULT_PIPELINE_CONFIG["enabled_phases"])
        assert actual == expected


class TestDefaultConversationConfig:
    def test_has_required_deliverables(self):
        assert "required_deliverables" in DEFAULT_CONVERSATION_CONFIG
        from arc.domain.project.value_objects import REQUIRED_DELIVERABLES
        assert len(DEFAULT_CONVERSATION_CONFIG["required_deliverables"]) == len(REQUIRED_DELIVERABLES)

    def test_agent_autonomy_is_supervised(self):
        assert DEFAULT_CONVERSATION_CONFIG["agent_autonomy"] == "supervised"

    def test_auto_archive_enabled(self):
        assert DEFAULT_CONVERSATION_CONFIG["auto_archive"] is True

    def test_loop_config_present(self):
        loop = DEFAULT_CONVERSATION_CONFIG["loop_config"]
        assert "token_budget" in loop
        assert "wall_timeout_seconds" in loop
        assert "max_tokens_per_call" in loop

    def test_loop_config_values_positive(self):
        loop = DEFAULT_CONVERSATION_CONFIG["loop_config"]
        assert loop["token_budget"] > 0
        assert loop["wall_timeout_seconds"] > 0
        assert loop["max_tokens_per_call"] > 0

    def test_git_sync_present(self):
        git = DEFAULT_CONVERSATION_CONFIG["git_sync"]
        assert "auto_commit" in git
        assert "auto_push" in git
        assert "commit_prefix" in git
        assert "target_branch" in git

    def test_git_sync_defaults_conservative(self):
        git = DEFAULT_CONVERSATION_CONFIG["git_sync"]
        assert git["auto_commit"] is False
        assert git["auto_push"] is False
