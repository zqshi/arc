"""Tests for domain/planning value objects."""

from arc.domain.planning.value_objects import (
    VALID_PLANNING_TRANSITIONS,
    DeliverableStatus,
    DocumentStatus,
    PlanningStatus,
)


class TestPlanningStatus:
    def test_enum_values_complete(self):
        expected = {"draft", "reviewing", "confirmed", "applied"}
        assert {ps.value for ps in PlanningStatus} == expected

    def test_enum_count(self):
        assert len(PlanningStatus) == 4

    def test_str_equality(self):
        assert PlanningStatus.DRAFT == "draft"
        assert PlanningStatus.REVIEWING == "reviewing"
        assert PlanningStatus.CONFIRMED == "confirmed"
        assert PlanningStatus.APPLIED == "applied"

    def test_identity_equality(self):
        assert PlanningStatus.DRAFT == PlanningStatus.DRAFT

    def test_from_value(self):
        assert PlanningStatus("confirmed") == PlanningStatus.CONFIRMED


class TestValidPlanningTransitions:
    def test_all_statuses_have_transitions(self):
        for ps in PlanningStatus:
            assert ps in VALID_PLANNING_TRANSITIONS

    def test_draft_can_go_to_reviewing(self):
        assert VALID_PLANNING_TRANSITIONS[PlanningStatus.DRAFT] == {
            PlanningStatus.REVIEWING,
        }

    def test_reviewing_can_go_to_confirmed_or_draft(self):
        assert VALID_PLANNING_TRANSITIONS[PlanningStatus.REVIEWING] == {
            PlanningStatus.CONFIRMED,
            PlanningStatus.DRAFT,
        }

    def test_confirmed_can_go_to_applied_or_draft(self):
        assert VALID_PLANNING_TRANSITIONS[PlanningStatus.CONFIRMED] == {
            PlanningStatus.APPLIED,
            PlanningStatus.DRAFT,
        }

    def test_applied_can_go_back_to_draft(self):
        assert VALID_PLANNING_TRANSITIONS[PlanningStatus.APPLIED] == {
            PlanningStatus.DRAFT,
        }

    def test_no_transition_to_self(self):
        for status, targets in VALID_PLANNING_TRANSITIONS.items():
            assert status not in targets

    def test_draft_is_always_reachable(self):
        """Every non-draft status can transition back to draft."""
        for status in PlanningStatus:
            if status != PlanningStatus.DRAFT:
                assert PlanningStatus.DRAFT in VALID_PLANNING_TRANSITIONS[status]


class TestDocumentStatus:
    def test_enum_values_complete(self):
        expected = {"uploading", "processing", "ready", "error"}
        assert {ds.value for ds in DocumentStatus} == expected

    def test_enum_count(self):
        assert len(DocumentStatus) == 4

    def test_str_equality(self):
        assert DocumentStatus.UPLOADING == "uploading"
        assert DocumentStatus.PROCESSING == "processing"
        assert DocumentStatus.READY == "ready"
        assert DocumentStatus.ERROR == "error"

    def test_identity_equality(self):
        assert DocumentStatus.READY == DocumentStatus.READY

    def test_from_value(self):
        assert DocumentStatus("error") == DocumentStatus.ERROR


class TestDeliverableStatus:
    def test_enum_values_complete(self):
        expected = {"pending", "in_progress", "produced", "confirmed"}
        assert {ds.value for ds in DeliverableStatus} == expected

    def test_enum_count(self):
        assert len(DeliverableStatus) == 4

    def test_str_equality(self):
        assert DeliverableStatus.PENDING == "pending"
        assert DeliverableStatus.IN_PROGRESS == "in_progress"
        assert DeliverableStatus.PRODUCED == "produced"
        assert DeliverableStatus.CONFIRMED == "confirmed"

    def test_identity_equality(self):
        assert DeliverableStatus.PENDING == DeliverableStatus.PENDING

    def test_from_value(self):
        assert DeliverableStatus("in_progress") == DeliverableStatus.IN_PROGRESS
