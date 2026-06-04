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


class TestGenerateChangelog:
    """v5.1.0: AI changelog 生成 + fallback 逻辑。"""

    @pytest.fixture
    def changelog_service(self, mock_db):
        with patch("arc.application.project.service.VersionRepository") as MockVRepo, \
             patch("arc.application.project.service.TodoRepository") as MockTRepo:
            MockVRepo.return_value = AsyncMock()
            MockTRepo.return_value = AsyncMock()
            svc = VersionService(mock_db)
            yield svc

    @pytest.mark.asyncio
    async def test_empty_todos_returns_empty(self, changelog_service):
        svc = changelog_service
        v = Version(project_id=uuid.uuid4(), name="v1.0")
        result = await svc._generate_changelog(v, [])
        assert result == ""

    @pytest.mark.asyncio
    async def test_fallback_on_llm_failure(self, changelog_service):
        """LLM 失败时降级为 bullet list。"""
        svc = changelog_service
        v = Version(project_id=uuid.uuid4(), name="v1.0", goal="MVP")

        todo1 = MagicMock()
        todo1.title = "用户登录"
        todo1.description = "实现 JWT 登录"
        todo2 = MagicMock()
        todo2.title = "注册功能"
        todo2.description = ""

        with patch("arc.application.ai.resilience.create_resilient_adapter", side_effect=Exception("no LLM")):
            result = await svc._generate_changelog(v, [todo1, todo2])

        assert "- 用户登录" in result
        assert "- 注册功能" in result

    @pytest.mark.asyncio
    async def test_llm_success(self, changelog_service):
        """LLM 成功时返回 AI 生成内容。"""
        svc = changelog_service
        v = Version(project_id=uuid.uuid4(), name="v1.0")

        todo = MagicMock()
        todo.title = "用户登录"
        todo.description = "JWT + 短信验证"

        mock_response = MagicMock()
        mock_response.content = "### 新功能\n- 用户登录（JWT + 短信验证码）"

        mock_adapter = AsyncMock()
        mock_adapter.chat = AsyncMock(return_value=mock_response)
        mock_adapter.close = AsyncMock()

        with patch("arc.application.ai.resilience.create_resilient_adapter", return_value=mock_adapter):
            result = await svc._generate_changelog(v, [todo])

        assert "用户登录" in result
        assert "新功能" in result

    @pytest.mark.asyncio
    async def test_llm_returns_empty_uses_fallback(self, changelog_service):
        """LLM 返回空内容时降级为 fallback。"""
        svc = changelog_service
        v = Version(project_id=uuid.uuid4(), name="v1.0")

        todo = MagicMock()
        todo.title = "修复BUG"
        todo.description = ""

        mock_response = MagicMock()
        mock_response.content = ""  # LLM returned empty

        mock_adapter = AsyncMock()
        mock_adapter.chat = AsyncMock(return_value=mock_response)
        mock_adapter.close = AsyncMock()

        with patch("arc.application.ai.resilience.create_resilient_adapter", return_value=mock_adapter):
            result = await svc._generate_changelog(v, [todo])

        assert "- 修复BUG" in result
