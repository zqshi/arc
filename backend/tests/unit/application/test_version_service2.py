"""VersionService 单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from arc.application.project.service import VersionService, _next_version_name
from arc.domain.errors import AppError
from arc.domain.project.entity import Version
from arc.domain.project.value_objects import VersionStatus


def _make_version(name: str, status: VersionStatus = VersionStatus.PLANNING) -> Version:
    return Version(project_id=uuid.uuid4(), name=name, status=status)


class TestNextVersionName:
    def test_first_minor(self):
        assert _next_version_name([], "minor") == "v0.1"

    def test_first_major(self):
        assert _next_version_name([], "major") == "v1.0"

    def test_increment_minor(self):
        versions = [_make_version("v1.2")]
        assert _next_version_name(versions, "minor") == "v1.3"

    def test_increment_major(self):
        versions = [_make_version("v1.2")]
        assert _next_version_name(versions, "major") == "v2.0"

    def test_increment_patch(self):
        versions = [_make_version("v1.2.3")]
        assert _next_version_name(versions, "patch") == "v1.2.4"

    def test_picks_latest(self):
        versions = [_make_version("v1.0"), _make_version("v2.1"), _make_version("v1.5")]
        assert _next_version_name(versions, "minor") == "v2.2"

    def test_ignores_non_semver(self):
        versions = [_make_version("alpha"), _make_version("v1.0")]
        assert _next_version_name(versions, "minor") == "v1.1"


class TestVersionServiceCreate:
    @pytest.fixture
    def svc(self):
        db = MagicMock()
        svc = VersionService.__new__(VersionService)
        svc.db = db
        svc.version_repo = MagicMock()
        svc.todo_repo = MagicMock()
        svc.version_repo._next_order = AsyncMock(return_value=3)
        svc.version_repo.create = AsyncMock(side_effect=lambda v: v)
        return svc

    @pytest.mark.asyncio
    async def test_create_with_explicit_name(self, svc):
        v = await svc.create_version(uuid.uuid4(), name="v1.0", goal="test")
        assert v.name == "v1.0"
        assert v.goal == "test"
        assert v.order == 3

    @pytest.mark.asyncio
    async def test_create_auto_name(self, svc):
        svc.version_repo.list_by_project = AsyncMock(
            return_value=[_make_version("v1.0")]
        )
        v = await svc.create_version(uuid.uuid4(), version_type="minor")
        assert v.name == "v1.1"


class TestVersionServiceDelete:
    @pytest.fixture
    def svc(self):
        svc = VersionService.__new__(VersionService)
        svc.version_repo = MagicMock()
        svc.todo_repo = MagicMock()
        return svc

    @pytest.mark.asyncio
    async def test_cannot_delete_released(self, svc):
        v = _make_version("v1.0", VersionStatus.RELEASED)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        with pytest.raises(AppError, match="已发布"):
            await svc.delete_version(v.project_id, v.id)

    @pytest.mark.asyncio
    async def test_cannot_delete_with_todos(self, svc):
        v = _make_version("v1.0", VersionStatus.PLANNING)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(return_value={"pending": 3})
        with pytest.raises(AppError, match="先删除"):
            await svc.delete_version(v.project_id, v.id)


class TestVersionServiceActivate:
    @pytest.fixture
    def svc(self):
        svc = VersionService.__new__(VersionService)
        svc.version_repo = MagicMock()
        svc.todo_repo = MagicMock()
        return svc

    @pytest.mark.asyncio
    async def test_activate_with_todos(self, svc):
        v = _make_version("v1.0", VersionStatus.PLANNING)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(return_value={"pending": 5})
        svc.version_repo.update = AsyncMock()

        result = await svc.activate_version(v.project_id, v.id)
        assert result.status == VersionStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_cannot_activate_empty(self, svc):
        v = _make_version("v1.0", VersionStatus.PLANNING)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(return_value={})

        with pytest.raises(AppError, match="没有需求"):
            await svc.activate_version(v.project_id, v.id)


class TestVersionServiceRelease:
    @pytest.fixture
    def svc(self):
        svc = VersionService.__new__(VersionService)
        svc.version_repo = MagicMock()
        svc.todo_repo = MagicMock()
        return svc

    @pytest.mark.asyncio
    async def test_cannot_release_with_incomplete(self, svc):
        v = _make_version("v1.0", VersionStatus.ACTIVE)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(
            return_value={"done": 3, "active": 1}
        )
        with pytest.raises(AppError, match="未完成"):
            await svc.release_version(v.project_id, v.id)
