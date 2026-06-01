"""Tests for domain/pipeline value objects."""

from arc.domain.pipeline.value_objects import (
    PHASE_LABELS,
    PHASE_ORDER,
    VALID_PHASE_TRANSITIONS,
    PhaseStatus,
    PhaseType,
    next_phase,
)


class TestPhaseType:
    def test_enum_values_complete(self):
        expected = {
            "clarification",
            "ui_design",
            "architecture",
            "development",
            "testing",
            "deployment",
            "extraction",
        }
        assert {pt.value for pt in PhaseType} == expected

    def test_enum_count(self):
        assert len(PhaseType) == 7

    def test_str_equality(self):
        assert PhaseType.CLARIFICATION == "clarification"
        assert PhaseType.DEVELOPMENT == "development"

    def test_identity_equality(self):
        assert PhaseType.TESTING == PhaseType.TESTING

    def test_from_value(self):
        assert PhaseType("architecture") == PhaseType.ARCHITECTURE


class TestPhaseStatus:
    def test_enum_values_complete(self):
        expected = {"pending", "active", "awaiting_confirm", "confirmed", "skipped"}
        assert {ps.value for ps in PhaseStatus} == expected

    def test_enum_count(self):
        assert len(PhaseStatus) == 5

    def test_str_equality(self):
        assert PhaseStatus.PENDING == "pending"
        assert PhaseStatus.AWAITING_CONFIRM == "awaiting_confirm"

    def test_identity_equality(self):
        assert PhaseStatus.ACTIVE == PhaseStatus.ACTIVE


class TestPhaseOrder:
    def test_all_phases_have_order(self):
        for pt in PhaseType:
            assert pt in PHASE_ORDER

    def test_order_sequential(self):
        orders = sorted(PHASE_ORDER.values())
        assert orders == list(range(1, 8))

    def test_clarification_first(self):
        assert PHASE_ORDER[PhaseType.CLARIFICATION] == 1

    def test_extraction_last(self):
        assert PHASE_ORDER[PhaseType.EXTRACTION] == 7


class TestPhaseLabels:
    def test_all_phases_have_label(self):
        for pt in PhaseType:
            assert pt in PHASE_LABELS

    def test_labels_are_nonempty_strings(self):
        for label in PHASE_LABELS.values():
            assert isinstance(label, str)
            assert len(label) > 0

    def test_specific_labels(self):
        assert PHASE_LABELS[PhaseType.CLARIFICATION] == "需求澄清"
        assert PHASE_LABELS[PhaseType.DEVELOPMENT] == "开发实现"


class TestValidPhaseTransitions:
    def test_all_statuses_have_transitions(self):
        for ps in PhaseStatus:
            assert ps in VALID_PHASE_TRANSITIONS

    def test_pending_can_go_to_active_or_skipped(self):
        assert VALID_PHASE_TRANSITIONS[PhaseStatus.PENDING] == {
            PhaseStatus.ACTIVE,
            PhaseStatus.SKIPPED,
        }

    def test_active_can_go_to_awaiting_confirm(self):
        assert VALID_PHASE_TRANSITIONS[PhaseStatus.ACTIVE] == {
            PhaseStatus.AWAITING_CONFIRM,
        }

    def test_awaiting_confirm_can_go_to_confirmed_or_active(self):
        assert VALID_PHASE_TRANSITIONS[PhaseStatus.AWAITING_CONFIRM] == {
            PhaseStatus.CONFIRMED,
            PhaseStatus.ACTIVE,
        }

    def test_confirmed_can_rollback_to_active(self):
        assert VALID_PHASE_TRANSITIONS[PhaseStatus.CONFIRMED] == {PhaseStatus.ACTIVE}

    def test_skipped_can_unskip_to_active(self):
        assert VALID_PHASE_TRANSITIONS[PhaseStatus.SKIPPED] == {PhaseStatus.ACTIVE}

    def test_no_transition_to_self(self):
        for status, targets in VALID_PHASE_TRANSITIONS.items():
            assert status not in targets


class TestNextPhase:
    def test_clarification_next_is_ui_design(self):
        assert next_phase(PhaseType.CLARIFICATION) == PhaseType.UI_DESIGN

    def test_ui_design_next_is_architecture(self):
        assert next_phase(PhaseType.UI_DESIGN) == PhaseType.ARCHITECTURE

    def test_architecture_next_is_development(self):
        assert next_phase(PhaseType.ARCHITECTURE) == PhaseType.DEVELOPMENT

    def test_development_next_is_testing(self):
        assert next_phase(PhaseType.DEVELOPMENT) == PhaseType.TESTING

    def test_testing_next_is_deployment(self):
        assert next_phase(PhaseType.TESTING) == PhaseType.DEPLOYMENT

    def test_deployment_next_is_extraction(self):
        assert next_phase(PhaseType.DEPLOYMENT) == PhaseType.EXTRACTION

    def test_extraction_next_is_none(self):
        assert next_phase(PhaseType.EXTRACTION) is None

    def test_sequential_traversal(self):
        """Verify we can walk through all phases in order."""
        current: PhaseType | None = PhaseType.CLARIFICATION
        visited = []
        while current is not None:
            visited.append(current)
            current = next_phase(current)
        assert len(visited) == 7
        assert visited[0] == PhaseType.CLARIFICATION
        assert visited[-1] == PhaseType.EXTRACTION
