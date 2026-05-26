"""Unit tests for VersionService."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.project.service import VersionService, _next_version_name
from arc.domain.project.entity import Version
from arc.domain.project.value_objects import VersionStatus


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def version_service(mock_db):
    with patch("arc.application.project.service.VersionRepository") as MockVRepo, \
         patch("arc.application.project.service.TodoRepository") as MockTRepo:
        mock_vrepo = AsyncMock()
        mock_trepo = AsyncMock()
        MockVRepo.return_value = mock_vrepo
        MockTRepo.return_value = mock_trepo

        svc = VersionService(mock_db)
        svc.version_repo = mock_vrepo
        svc.todo_repo = mock_trepo
        yield svc


class TestNextVersionName:
    def test_first_version_minor(self):
        assert _next_version_name([], "minor") == "v0.1"

    def test_first_version_major(self):
        assert _next_version_name([], "major") == "v1.0"

    def test_increment_minor(self):
        versions = [MagicMock(name="v1.3")]
        versions[0].name = "v1.3"
        assert _next_version_name(versions, "minor") == "v1.4"

    def test_increment_major(self):
        versions = [MagicMock(name="v2.5")]
        versions[0].name = "v2.5"
        assert _next_version_name(versions, "major") == "v3.0"

    def test_increment_patch(self):
        versions = [MagicMock(name="v1.2.3")]
        versions[0].name = "v1.2.3"
        assert _next_version_name(versions, "patch") == "v1.2.4"

    def test_picks_highest(self):
        versions = [MagicMock(), MagicMock(), MagicMock()]
        versions[0].name = "v0.1"
        versions[1].name = "v1.0"
        versions[2].name = "v0.9"
        assert _next_version_name(versions, "minor") == "v1.1"


class TestCreateVersion:
    @pytest.mark.asyncio
    async def test_create_with_explicit_name(self, version_service):
        svc = version_service
        project_id = uuid.uuid4()
        svc.version_repo._next_order = AsyncMock(return_value=1)
        svc.version_repo.create = AsyncMock(side_effect=lambda v: v)

        version = await svc.create_version(project_id, name="  v2.0  ", goal="test")
        assert version.name == "v2.0"
        assert version.project_id == project_id

    @pytest.mark.asyncio
    async def test_create_auto_name(self, version_service):
        svc = version_service
        project_id = uuid.uuid4()
        svc.version_repo._next_order = AsyncMock(return_value=2)
        existing = MagicMock()
        existing.name = "v1.0"
        svc.version_repo.list_by_project = AsyncMock(return_value=[existing])
        svc.version_repo.create = AsyncMock(side_effect=lambda v: v)

        version = await svc.create_version(project_id, goal="next")
        assert version.name == "v1.1"


class TestDeleteVersion:
    @pytest.mark.asyncio
    async def test_cannot_delete_released(self, version_service):
        svc = version_service
        v = Version(project_id=uuid.uuid4(), name="v1.0", status=VersionStatus.RELEASED)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(return_value={})

        with pytest.raises(ValueError, match="已发布"):
            await svc.delete_version(v.project_id, v.id)

    @pytest.mark.asyncio
    async def test_cannot_delete_with_todos(self, version_service):
        svc = version_service
        v = Version(project_id=uuid.uuid4(), name="v1.0")
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(return_value={"pending": 2})

        with pytest.raises(ValueError, match="需求"):
            await svc.delete_version(v.project_id, v.id)

    @pytest.mark.asyncio
    async def test_delete_success(self, version_service):
        svc = version_service
        v = Version(project_id=uuid.uuid4(), name="v1.0")
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(return_value={})
        svc.version_repo.delete = AsyncMock()

        await svc.delete_version(v.project_id, v.id)
        svc.version_repo.delete.assert_called_once_with(v.id)


class TestActivateVersion:
    @pytest.mark.asyncio
    async def test_cannot_activate_empty(self, version_service):
        svc = version_service
        v = Version(project_id=uuid.uuid4(), name="v1.0")
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(return_value={})

        with pytest.raises(ValueError, match="没有需求"):
            await svc.activate_version(v.project_id, v.id)
