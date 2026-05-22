from __future__ import annotations

import uuid

import pytest

from arc.domain.pipeline.entity import InvalidPhaseTransitionError, PipelinePhase
from arc.domain.pipeline.value_objects import (
    PHASE_ORDER,
    PhaseStatus,
    PhaseType,
    next_phase,
)


class TestPhaseValueObjects:
    def test_phase_order_covers_all_types(self) -> None:
        for pt in PhaseType:
            assert pt in PHASE_ORDER

    def test_next_phase(self) -> None:
        assert next_phase(PhaseType.CLARIFICATION) == PhaseType.UI_DESIGN
        assert next_phase(PhaseType.UI_DESIGN) == PhaseType.ARCHITECTURE
        assert next_phase(PhaseType.ARCHITECTURE) == PhaseType.DEVELOPMENT
        assert next_phase(PhaseType.DEPLOYMENT) == PhaseType.EXTRACTION
        assert next_phase(PhaseType.EXTRACTION) is None


class TestPipelinePhaseTransitions:
    def _make_phase(self, status: PhaseStatus = PhaseStatus.PENDING) -> PipelinePhase:
        phase = PipelinePhase(
            todo_id=uuid.uuid4(),
            phase_type=PhaseType.CLARIFICATION,
        )
        phase.status = status
        return phase

    def test_activate_from_pending(self) -> None:
        phase = self._make_phase()
        phase.activate()
        assert phase.status == PhaseStatus.ACTIVE

    def test_mark_awaiting_confirm(self) -> None:
        phase = self._make_phase(PhaseStatus.ACTIVE)
        phase.mark_awaiting_confirm()
        assert phase.status == PhaseStatus.AWAITING_CONFIRM

    def test_confirm(self) -> None:
        phase = self._make_phase(PhaseStatus.AWAITING_CONFIRM)
        phase.confirm()
        assert phase.status == PhaseStatus.CONFIRMED

    def test_skip(self) -> None:
        phase = self._make_phase()
        phase.skip()
        assert phase.status == PhaseStatus.SKIPPED

    def test_rollback_from_confirmed(self) -> None:
        phase = self._make_phase(PhaseStatus.CONFIRMED)
        phase.reset_for_rollback()
        assert phase.status == PhaseStatus.ACTIVE

    def test_invalid_transition(self) -> None:
        phase = self._make_phase(PhaseStatus.PENDING)
        with pytest.raises(InvalidPhaseTransitionError):
            phase.confirm()

    def test_cannot_confirm_from_pending(self) -> None:
        phase = self._make_phase(PhaseStatus.PENDING)
        with pytest.raises(InvalidPhaseTransitionError):
            phase.mark_awaiting_confirm()
