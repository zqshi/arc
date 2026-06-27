"""ArtifactService 单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.errors import AppError
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

    @pytest.mark.asyncio
    async def test_update_rejects_non_editable_fields(self):
        """v5.5.0: APP_CODE 是 Agent 写入产物，用户不应能改 project_dir。"""
        from arc.application.artifact.service import ArtifactService

        art = Artifact(
            todo_id=uuid.uuid4(),
            artifact_type=ArtifactType.APP_CODE,
            content={"project_dir": "generated/app", "tech_stack": ["react"]},
        )

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=art)
        svc.artifact_repo.update = AsyncMock(side_effect=lambda a: a)

        with pytest.raises(AppError, match="不可编辑字段"):
            await svc.update_content(
                art.id, {"project_dir": "hacked/path", "tech_stack": ["vue"]}
            )

    @pytest.mark.asyncio
    async def test_update_partial_merges_only_editable(self):
        """v5.5.0: partial 模式下 SERVICE_SPEC 只合并 notes，拒绝其他字段。"""
        from arc.application.artifact.service import ArtifactService

        art = Artifact(
            todo_id=uuid.uuid4(),
            artifact_type=ArtifactType.SERVICE_SPEC,
            content={
                "data_persistence": "none",
                "notes": "old note",
                "endpoints": [],
            },
        )

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=art)
        svc.artifact_repo.update = AsyncMock(side_effect=lambda a: a)

        with pytest.raises(AppError, match="不可编辑字段"):
            await svc.update_content(
                art.id, {"notes": "new note", "data_persistence": "supabase"},
                partial=True,
            )

    @pytest.mark.asyncio
    async def test_update_partial_allows_editable_only(self):
        """v5.5.0: partial 模式下 SERVICE_SPEC.notes 可改，其他字段保留。"""
        from arc.application.artifact.service import ArtifactService

        art = Artifact(
            todo_id=uuid.uuid4(),
            artifact_type=ArtifactType.SERVICE_SPEC,
            content={
                "data_persistence": "none",
                "notes": "old note",
                "endpoints": [{"method": "GET", "path": "/api/users"}],
            },
        )

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=art)
        svc.artifact_repo.update = AsyncMock(side_effect=lambda a: a)

        result = await svc.update_content(art.id, {"notes": "updated"}, partial=True)
        assert result.content["notes"] == "updated"
        # 其他字段保留
        assert result.content["data_persistence"] == "none"
        assert result.content["endpoints"] == [{"method": "GET", "path": "/api/users"}]


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


class TestArtifactServiceBuild:
    """v6.9: BUILD artifact 构建产物锚点操作。"""

    @pytest.mark.asyncio
    async def test_create_or_update_build_creates_when_absent(self):
        from arc.application.artifact.service import ArtifactService

        todo_id = uuid.uuid4()
        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.list_by_todo_id = AsyncMock(return_value=[])

        def _capture(art):
            return art

        svc.artifact_repo.create = AsyncMock(side_effect=_capture)
        svc.artifact_repo.update = AsyncMock()  # create 路径不应调 update

        result = await svc.create_or_update_build(
            todo_id,
            phase_id=None,
            build_target="tauri_linux",
            artifact_path="dist",
            build_status="success",
        )
        svc.artifact_repo.create.assert_awaited_once()
        svc.artifact_repo.update.assert_not_awaited()
        assert result.artifact_type == ArtifactType.BUILD
        assert result.content["build_target"] == "tauri_linux"
        assert result.content["artifact_path"] == "dist"
        assert result.content["build_status"] == "success"

    @pytest.mark.asyncio
    async def test_create_or_update_build_updates_when_exists(self):
        from arc.application.artifact.service import ArtifactService

        todo_id = uuid.uuid4()
        existing = Artifact(
            todo_id=todo_id,
            artifact_type=ArtifactType.BUILD,
            content={
                "build_target": "tauri_linux",
                "artifact_path": "dist",
                "build_status": "pending",
            },
        )
        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.list_by_todo_id = AsyncMock(return_value=[existing])
        svc.artifact_repo.update = AsyncMock(side_effect=lambda a: a)
        svc.artifact_repo.create = AsyncMock()  # update 路径不应调 create

        result = await svc.create_or_update_build(
            todo_id,
            phase_id=None,
            build_target="tauri_linux",
            artifact_path="dist",
            build_status="success",
        )
        svc.artifact_repo.create.assert_not_awaited()
        svc.artifact_repo.update.assert_awaited_once()
        assert result.content["build_status"] == "success"
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_update_build_status_merges_incrementally(self):
        """④接入点: 签名/分发状态增量回写, 不覆盖已有字段。"""
        from arc.application.artifact.service import ArtifactService

        art = Artifact(
            todo_id=uuid.uuid4(),
            artifact_type=ArtifactType.BUILD,
            content={
                "build_target": "web",
                "artifact_path": "dist",
                "build_status": "success",
            },
        )
        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=art)
        svc.artifact_repo.update = AsyncMock(side_effect=lambda a: a)

        result = await svc.update_build_status(
            art.id, signature_status="signed", product_path="/path/app.app"
        )
        assert result.content["build_status"] == "success"  # 保留
        assert result.content["signature_status"] == "signed"  # 新增
        assert result.content["product_path"] == "/path/app.app"

    @pytest.mark.asyncio
    async def test_update_build_status_rejects_non_build(self):
        from arc.application.artifact.service import ArtifactService

        art = Artifact(
            todo_id=uuid.uuid4(),
            artifact_type=ArtifactType.PROTOTYPE,
            content={"project_dir": "x"},
        )
        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=art)

        with pytest.raises(AppError, match="仅适用 BUILD"):
            await svc.update_build_status(art.id, build_status="success")

    @pytest.mark.asyncio
    async def test_update_build_status_not_found(self):
        from arc.application.artifact.service import ArtifactService

        svc = ArtifactService.__new__(ArtifactService)
        svc.artifact_repo = MagicMock()
        svc.artifact_repo.get_by_id = AsyncMock(return_value=None)

        assert await svc.update_build_status(uuid.uuid4(), build_status="success") is None
