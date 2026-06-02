"""ArtifactService 单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.pipeline.value_objects import PhaseType


class TestArtifactServiceUpdateContent:
    @pytest.mark.asyncio
    async def test_update_existing(self):
        from arc.application.artifact.service import ArtifactService

        art = Artifact(
            todo_id=uuid.uuid4(),
            artifact_type=ArtifactType.REQUIREMENT_SPEC,
            content={"old": True},
        )

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=art)
        svc.artifact_repo.update = AsyncMock(side_effect=lambda a: a)

        result = await svc.update_content(art.id, {"new": True})
        assert result.content == {"new": True}
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        from arc.application.artifact.service import ArtifactService

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=None)

        result = await svc.update_content(uuid.uuid4(), {})
        assert result is None


class TestArtifactServiceConfirm:
    @pytest.mark.asyncio
    async def test_confirm_with_content(self):
        from arc.application.artifact.service import ArtifactService

        art = Artifact(
            todo_id=uuid.uuid4(),
            artifact_type=ArtifactType.TECH_ARCHITECTURE,
            content={"data_model": {}},
        )

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=art)
        svc.artifact_repo.update = AsyncMock(side_effect=lambda a: a)

        result = await svc.confirm(art.id)
        assert result.is_confirmed is True

    @pytest.mark.asyncio
    async def test_confirm_empty_content_raises(self):
        from arc.application.artifact.service import ArtifactService

        art = Artifact(
            todo_id=uuid.uuid4(),
            artifact_type=ArtifactType.TECH_ARCHITECTURE,
            content={},
        )

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=art)

        with pytest.raises(ValueError, match="empty content"):
            await svc.confirm(art.id)

    @pytest.mark.asyncio
    async def test_confirm_not_found(self):
        from arc.application.artifact.service import ArtifactService

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=None)

        result = await svc.confirm(uuid.uuid4())
        assert result is None


class TestArtifactServiceGetConfirmedContext:
    @pytest.mark.asyncio
    async def test_returns_keyed_by_type(self):
        from arc.application.artifact.service import ArtifactService

        todo_id = uuid.uuid4()
        arts = [
            Artifact(todo_id=todo_id, artifact_type=ArtifactType.REQUIREMENT_SPEC,
                     content={"bg": "x"}, is_confirmed=True),
            Artifact(todo_id=todo_id, artifact_type=ArtifactType.TECH_ARCHITECTURE,
                     content={"dm": "y"}, is_confirmed=True),
        ]

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.list_confirmed_by_todo = AsyncMock(return_value=arts)

        result = await svc.get_confirmed_context(todo_id)
        assert ArtifactType.REQUIREMENT_SPEC in result
        assert ArtifactType.TECH_ARCHITECTURE in result

    @pytest.mark.asyncio
    async def test_empty(self):
        from arc.application.artifact.service import ArtifactService

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.list_confirmed_by_todo = AsyncMock(return_value=[])

        result = await svc.get_confirmed_context(uuid.uuid4())
        assert result == {}


class TestGetExtractionPrompt:
    def test_known_phase(self):
        from arc.application.artifact.service import ArtifactService

        prompt = ArtifactService._get_extraction_prompt(PhaseType.CLARIFICATION)
        assert prompt is not None and len(prompt) > 0

    def test_unknown_returns_none(self):
        from arc.application.artifact.service import ArtifactService

        prompt = ArtifactService._get_extraction_prompt("nonexistent")
        assert prompt is None
