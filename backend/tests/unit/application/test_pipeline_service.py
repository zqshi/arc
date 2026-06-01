"""Tests for application/pipeline service — initialization & state logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.domain.pipeline.value_objects import PhaseType


class TestPipelineServiceInit:
    """Test pipeline initialization logic without DB."""

    def test_phase_order(self):
        """Verify the canonical phase execution order."""
        from arc.domain.pipeline.value_objects import PHASE_ORDER
        assert PhaseType.CLARIFICATION in PHASE_ORDER
        assert PhaseType.DEVELOPMENT in PHASE_ORDER
        # Clarification should have lower order number than development
        assert PHASE_ORDER[PhaseType.CLARIFICATION] < PHASE_ORDER[PhaseType.DEVELOPMENT]

    def test_phase_type_values(self):
        """All phase types should be valid string enums."""
        for pt in PhaseType:
            assert isinstance(pt.value, str)
            assert len(pt.value) > 0
