from __future__ import annotations

import uuid

import pytest

from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType


class TestArtifactCreation:
    def test_defaults(self) -> None:
        a = Artifact(
            todo_id=uuid.uuid4(),
            phase_id=uuid.uuid4(),
            artifact_type=ArtifactType.REQUIREMENT_SPEC,
        )
        assert a.version == 1
        assert a.is_confirmed is False
        assert a.content == {}
        assert a.confirmed_at is None


class TestArtifactUpdate:
    def _make(self) -> Artifact:
        return Artifact(
            todo_id=uuid.uuid4(),
            phase_id=uuid.uuid4(),
            artifact_type=ArtifactType.REQUIREMENT_SPEC,
            content={"background": "old"},
        )

    def test_update_increments_version(self) -> None:
        a = self._make()
        a.update_content({"background": "new"})
        assert a.version == 2
        assert a.content == {"background": "new"}

    def test_update_unconfirms(self) -> None:
        a = self._make()
        a.confirm()
        assert a.is_confirmed is True
        a.update_content({"background": "changed"})
        assert a.is_confirmed is False
        assert a.confirmed_at is None

    def test_no_op_update(self) -> None:
        a = self._make()
        a.update_content({"background": "old"})
        assert a.version == 1

    def test_confirm(self) -> None:
        a = self._make()
        a.confirm()
        assert a.is_confirmed is True
        assert a.confirmed_at is not None

    def test_confirm_empty_raises(self) -> None:
        a = Artifact(
            todo_id=uuid.uuid4(),
            phase_id=uuid.uuid4(),
            artifact_type=ArtifactType.REQUIREMENT_SPEC,
        )
        with pytest.raises(ValueError, match="empty content"):
            a.confirm()

    def test_unconfirm(self) -> None:
        a = self._make()
        a.confirm()
        a.unconfirm()
        assert a.is_confirmed is False
        assert a.confirmed_at is None
