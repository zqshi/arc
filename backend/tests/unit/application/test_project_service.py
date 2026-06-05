"""VersionService 单元测试。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.domain.project.entity import Version
from arc.domain.project.value_objects import VersionStatus


def _make_service():
    """构造 VersionService 并注入 mock repository。"""
    from arc.application.project.service import VersionService

    svc = VersionService.__new__(VersionService)
    svc.db = MagicMock()
    svc.version_repo = MagicMock()
    svc.todo_repo = MagicMock()
    return svc


class TestCreateVersion:
    async def test_create_with_explicit_name(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()

        svc.version_repo._next_order = AsyncMock(return_value=1)
        svc.version_repo.create = AsyncMock(
            side_effect=lambda v: v
        )

        result = await svc.create_version(project_id, name="v2.0", goal="新版本")

        assert result.name == "v2.0"
        assert result.goal == "新版本"
        assert result.project_id == project_id
        assert result.order == 1

    async def test_create_auto_names_minor(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()

        existing = [
            Version(project_id=project_id, name="v1.0"),
            Version(project_id=project_id, name="v1.1"),
        ]
        svc.version_repo._next_order = AsyncMock(return_value=3)
        svc.version_repo.list_by_project = AsyncMock(return_value=existing)
        svc.version_repo.create = AsyncMock(side_effect=lambda v: v)

        result = await svc.create_version(project_id, version_type="minor")

        assert result.name == "v1.2"

    async def test_create_auto_names_major(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()

        existing = [Version(project_id=project_id, name="v2.3")]
        svc.version_repo._next_order = AsyncMock(return_value=2)
        svc.version_repo.list_by_project = AsyncMock(return_value=existing)
        svc.version_repo.create = AsyncMock(side_effect=lambda v: v)

        result = await svc.create_version(project_id, version_type="major")

        assert result.name == "v3.0"

    async def test_create_first_version_minor(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()

        svc.version_repo._next_order = AsyncMock(return_value=0)
        svc.version_repo.list_by_project = AsyncMock(return_value=[])
        svc.version_repo.create = AsyncMock(side_effect=lambda v: v)

        result = await svc.create_version(project_id, version_type="minor")

        assert result.name == "v0.1"


class TestDeleteVersion:
    async def test_delete_released_raises(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        v = Version(project_id=project_id, name="v1.0", id=version_id)
        v.activate()
        v.release()
        svc.version_repo.get_by_id = AsyncMock(return_value=v)

        with pytest.raises(ValueError, match="已发布版本不可删除"):
            await svc.delete_version(project_id, version_id)

    async def test_delete_with_todos_raises(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        v = Version(project_id=project_id, name="v1.0", id=version_id)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(
            return_value={"pending": 2, "done": 1}
        )

        with pytest.raises(ValueError, match="请先删除版本下的需求"):
            await svc.delete_version(project_id, version_id)

    async def test_delete_empty_planning_version_succeeds(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        v = Version(project_id=project_id, name="v1.0", id=version_id)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(return_value={})
        svc.version_repo.delete = AsyncMock()

        await svc.delete_version(project_id, version_id)
        svc.version_repo.delete.assert_awaited_once_with(version_id)


class TestActivateVersion:
    async def test_activate_with_todos_succeeds(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        v = Version(project_id=project_id, name="v1.0", id=version_id)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(
            return_value={"pending": 3}
        )
        svc.version_repo.update = AsyncMock()

        result = await svc.activate_version(project_id, version_id)

        assert result.status == VersionStatus.ACTIVE

    async def test_activate_empty_version_raises(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        v = Version(project_id=project_id, name="v1.0", id=version_id)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(return_value={})

        with pytest.raises(ValueError, match="版本下没有需求"):
            await svc.activate_version(project_id, version_id)


class TestReleaseVersion:
    async def test_release_with_incomplete_todos_raises(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        v = Version(project_id=project_id, name="v1.0", id=version_id)
        v.activate()
        svc.version_repo.get_by_id = AsyncMock(return_value=v)
        svc.version_repo.count_todos_by_status = AsyncMock(
            return_value={"pending": 2, "active": 1, "done": 5}
        )

        with pytest.raises(ValueError, match="未完成需求"):
            await svc.release_version(project_id, version_id)


class TestGetVersion:
    async def test_version_not_found_raises(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        svc.version_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="版本不存在"):
            await svc._get_version(project_id, version_id)

    async def test_version_wrong_project_raises(self) -> None:
        svc = _make_service()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        v = Version(project_id=uuid.uuid4(), name="v1.0", id=version_id)
        svc.version_repo.get_by_id = AsyncMock(return_value=v)

        with pytest.raises(ValueError, match="版本不存在"):
            await svc._get_version(project_id, version_id)


class TestNextVersionName:
    """测试 _next_version_name 辅助函数。"""

    def test_empty_list_minor(self) -> None:
        from arc.application.project.service import _next_version_name
        result = _next_version_name([], "minor")
        assert result == "v0.1"

    def test_empty_list_major(self) -> None:
        from arc.application.project.service import _next_version_name
        result = _next_version_name([], "major")
        assert result == "v1.0"

    def test_increment_minor(self) -> None:
        from arc.application.project.service import _next_version_name
        versions = [
            Version(project_id=uuid.uuid4(), name="v1.2"),
        ]
        result = _next_version_name(versions, "minor")
        assert result == "v1.3"

    def test_increment_patch(self) -> None:
        from arc.application.project.service import _next_version_name
        versions = [
            Version(project_id=uuid.uuid4(), name="v2.1.3"),
        ]
        result = _next_version_name(versions, "patch")
        assert result == "v2.1.4"

    def test_picks_latest_version(self) -> None:
        from arc.application.project.service import _next_version_name
        pid = uuid.uuid4()
        versions = [
            Version(project_id=pid, name="v1.0"),
            Version(project_id=pid, name="v2.1"),
            Version(project_id=pid, name="v1.5"),
        ]
        result = _next_version_name(versions, "major")
        assert result == "v3.0"
