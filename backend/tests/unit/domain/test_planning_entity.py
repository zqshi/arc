from __future__ import annotations

import uuid

import pytest

from arc.domain.planning.entity import DeliverableTracker, Document, PlanningSession
from arc.domain.planning.value_objects import (
    DeliverableStatus,
    DocumentStatus,
    PlanningStatus,
)


class TestDocumentCreation:
    def test_defaults(self) -> None:
        d = Document(
            project_id=uuid.uuid4(),
            filename="spec.pdf",
            content_type="application/pdf",
            size=1024,
        )
        assert d.status == DocumentStatus.UPLOADING
        assert d.storage_path == ""
        assert d.extracted_text == ""
        assert d.parsed_features == []

    def test_full_fields(self) -> None:
        pid = uuid.uuid4()
        d = Document(
            project_id=pid,
            filename="arch.md",
            content_type="text/markdown",
            size=2048,
            storage_path="/uploads/arch.md",
            extracted_text="hello",
            parsed_features=[{"name": "auth"}],
            status=DocumentStatus.READY,
        )
        assert d.project_id == pid
        assert d.extracted_text == "hello"
        assert d.status == DocumentStatus.READY


class TestDocumentStatusTransitions:
    def _make(self) -> Document:
        return Document(
            project_id=uuid.uuid4(),
            filename="req.pdf",
            content_type="application/pdf",
            size=512,
        )

    def test_mark_processing(self) -> None:
        d = self._make()
        d.mark_processing()
        assert d.status == DocumentStatus.PROCESSING

    def test_mark_ready(self) -> None:
        d = self._make()
        features = [{"name": "login"}, {"name": "signup"}]
        d.mark_ready("extracted text here", features)
        assert d.status == DocumentStatus.READY
        assert d.extracted_text == "extracted text here"
        assert d.parsed_features == features

    def test_mark_error(self) -> None:
        d = self._make()
        d.mark_error()
        assert d.status == DocumentStatus.ERROR


class TestPlanningSessionCreation:
    def test_defaults(self) -> None:
        s = PlanningSession(project_id=uuid.uuid4())
        assert s.status == PlanningStatus.DRAFT
        assert s.version_id is None
        assert s.document_ids == []
        assert s.constraints == {}
        assert s.roadmap == {}
        assert s.conversation_id is None


class TestPlanningSessionTransitions:
    def _make(self) -> PlanningSession:
        return PlanningSession(project_id=uuid.uuid4())

    def test_submit_for_review(self) -> None:
        s = self._make()
        roadmap = {"phases": ["clarification", "dev"]}
        s.submit_for_review(roadmap)
        assert s.status == PlanningStatus.REVIEWING
        assert s.roadmap == roadmap

    def test_confirm_from_reviewing(self) -> None:
        s = self._make()
        s.submit_for_review({"phases": []})
        s.confirm()
        assert s.status == PlanningStatus.CONFIRMED

    def test_apply_from_confirmed(self) -> None:
        s = self._make()
        s.submit_for_review({})
        s.confirm()
        s.apply()
        assert s.status == PlanningStatus.APPLIED

    def test_revise_from_reviewing(self) -> None:
        s = self._make()
        s.submit_for_review({})
        s.revise()
        assert s.status == PlanningStatus.DRAFT

    def test_revise_from_confirmed(self) -> None:
        s = self._make()
        s.submit_for_review({})
        s.confirm()
        s.revise()
        assert s.status == PlanningStatus.DRAFT

    def test_revise_from_applied(self) -> None:
        s = self._make()
        s.submit_for_review({})
        s.confirm()
        s.apply()
        s.revise()
        assert s.status == PlanningStatus.DRAFT

    def test_invalid_transition_confirm_from_draft(self) -> None:
        s = self._make()
        with pytest.raises(ValueError, match="Cannot transition"):
            s.confirm()

    def test_invalid_transition_apply_from_draft(self) -> None:
        s = self._make()
        with pytest.raises(ValueError, match="Cannot transition"):
            s.apply()

    def test_invalid_transition_apply_from_reviewing(self) -> None:
        s = self._make()
        s.submit_for_review({})
        with pytest.raises(ValueError, match="Cannot transition"):
            s.apply()

    def test_update_constraints(self) -> None:
        s = self._make()
        before = s.updated_at
        s.update_constraints({"budget": 100})
        assert s.constraints == {"budget": 100}
        assert s.updated_at >= before


class TestDeliverableTrackerCreation:
    def test_defaults(self) -> None:
        t = DeliverableTracker(todo_id=uuid.uuid4())
        assert t.required == []
        assert t.deliverables == {}
        assert t.completion_pct == 0.0
        assert t.is_complete is False


class TestDeliverableTrackerBehavior:
    def _make(self) -> DeliverableTracker:
        t = DeliverableTracker(todo_id=uuid.uuid4())
        t.initialize(["requirement_spec", "test_report", "dev_report"])
        return t

    def test_initialize(self) -> None:
        t = self._make()
        assert t.required == ["requirement_spec", "test_report", "dev_report"]
        assert all(s == DeliverableStatus.PENDING for s in t.deliverables.values())

    def test_mark_in_progress(self) -> None:
        t = self._make()
        t.mark_in_progress("requirement_spec")
        assert t.deliverables["requirement_spec"] == DeliverableStatus.IN_PROGRESS

    def test_mark_in_progress_unknown_type_noop(self) -> None:
        t = self._make()
        t.mark_in_progress("nonexistent")
        assert "nonexistent" not in t.deliverables

    def test_mark_produced(self) -> None:
        t = self._make()
        t.mark_produced("requirement_spec")
        assert t.deliverables["requirement_spec"] == DeliverableStatus.PRODUCED

    def test_mark_confirmed(self) -> None:
        t = self._make()
        t.mark_confirmed("requirement_spec")
        assert t.deliverables["requirement_spec"] == DeliverableStatus.CONFIRMED

    def test_mark_confirmed_unknown_type_noop(self) -> None:
        t = self._make()
        t.mark_confirmed("nonexistent")
        assert "nonexistent" not in t.deliverables

    def test_completion_pct_partial(self) -> None:
        t = self._make()
        t.mark_produced("requirement_spec")
        assert t.completion_pct == pytest.approx(0.33, abs=0.01)

    def test_completion_pct_full(self) -> None:
        t = self._make()
        for typ in t.required:
            t.mark_produced(typ)
        assert t.completion_pct == 1.0

    def test_is_complete_false_when_partial(self) -> None:
        t = self._make()
        t.mark_produced("requirement_spec")
        assert t.is_complete is False

    def test_is_complete_true_when_all_produced(self) -> None:
        t = self._make()
        for typ in t.required:
            t.mark_produced(typ)
        assert t.is_complete is True

    def test_is_complete_true_with_mix_of_produced_and_confirmed(self) -> None:
        t = self._make()
        t.mark_produced("requirement_spec")
        t.mark_confirmed("test_report")
        t.mark_produced("dev_report")
        assert t.is_complete is True

    def test_is_complete_false_when_empty(self) -> None:
        t = DeliverableTracker(todo_id=uuid.uuid4())
        assert t.is_complete is False
