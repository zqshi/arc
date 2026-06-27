"""Tests for ARCHITECTURE 阶段 BaaS provision hook (v5.6.0 T11).

领域模型提取成功后自动触发 BaaS provision + apply。
hook 内部用方法内 import, 测试 patch 真实 repo 源模块 + Applier 源模块。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.execution.artifact_post_process import ArtifactPostProcessHooks
from arc.domain.project.value_objects import DomainModelSnapshot


def _make_project_with_model(*, has_aggregates: bool = True):
    project = MagicMock()
    project.id = uuid.uuid4()
    if has_aggregates:
        project.domain_model = {
            "version": 1,
            "aggregates": [{"name": "Post", "fields": ["id", "title"]}],
        }
    else:
        project.domain_model = {"version": 1, "aggregates": []}
    return project


class TestTryProvisionBaasAfterExtract:
    @pytest.mark.asyncio
    async def test_provision_triggered_when_model_has_aggregates(self):
        """领域模型含聚合 → 调 DomainModelApplier.apply_snapshot。"""
        from arc.application.execution.artifact_extractor import ArtifactExtractor

        todo = MagicMock()
        todo.project_id = uuid.uuid4()
        project = _make_project_with_model(has_aggregates=True)

        extractor = ArtifactExtractor.__new__(ArtifactExtractor)
        extractor.db = MagicMock()
        extractor._hooks = ArtifactPostProcessHooks(extractor.db, None)

        with patch(
            "arc.infrastructure.repositories.todo.TodoRepository"
        ) as MockTodoRepo, patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.application.baas.domain_model_applier.DomainModelApplier"
        ) as MockApplier, patch(
            "arc.application.baas.service.BaasService"
        ):
            MockTodoRepo.return_value.get_by_id = AsyncMock(return_value=todo)
            MockProjRepo.return_value.get_by_id = AsyncMock(return_value=project)
            mock_applier = MagicMock()
            mock_applier.apply_snapshot = AsyncMock()
            MockApplier.return_value = mock_applier

            await extractor._hooks.try_provision_baas_after_extract(uuid.uuid4())

            mock_applier.apply_snapshot.assert_awaited_once()
            call_kwargs = mock_applier.apply_snapshot.call_args.kwargs
            assert call_kwargs["project_id"] == project.id
            assert isinstance(call_kwargs["snapshot"], DomainModelSnapshot)
            assert call_kwargs["snapshot"].version == 1

    @pytest.mark.asyncio
    async def test_provision_skipped_when_no_aggregates(self):
        from arc.application.execution.artifact_extractor import ArtifactExtractor

        todo = MagicMock()
        todo.project_id = uuid.uuid4()
        project = _make_project_with_model(has_aggregates=False)

        extractor = ArtifactExtractor.__new__(ArtifactExtractor)
        extractor.db = MagicMock()
        extractor._hooks = ArtifactPostProcessHooks(extractor.db, None)

        with patch(
            "arc.infrastructure.repositories.todo.TodoRepository"
        ) as MockTodoRepo, patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.application.baas.domain_model_applier.DomainModelApplier"
        ) as MockApplier:
            MockTodoRepo.return_value.get_by_id = AsyncMock(return_value=todo)
            MockProjRepo.return_value.get_by_id = AsyncMock(return_value=project)
            mock_applier = MagicMock()
            mock_applier.apply_snapshot = AsyncMock()
            MockApplier.return_value = mock_applier

            await extractor._hooks.try_provision_baas_after_extract(uuid.uuid4())

            mock_applier.apply_snapshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_provision_skipped_when_no_project(self):
        from arc.application.execution.artifact_extractor import ArtifactExtractor

        todo = MagicMock()
        todo.project_id = None

        extractor = ArtifactExtractor.__new__(ArtifactExtractor)
        extractor.db = MagicMock()
        extractor._hooks = ArtifactPostProcessHooks(extractor.db, None)

        with patch(
            "arc.infrastructure.repositories.todo.TodoRepository"
        ) as MockTodoRepo, patch(
            "arc.application.baas.domain_model_applier.DomainModelApplier"
        ) as MockApplier:
            MockTodoRepo.return_value.get_by_id = AsyncMock(return_value=todo)
            mock_applier = MagicMock()
            MockApplier.return_value = mock_applier

            await extractor._hooks.try_provision_baas_after_extract(uuid.uuid4())

            mock_applier.apply_snapshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_provision_failure_does_not_raise(self):
        """BaaS provision 失败不阻断主流程 (仅 warning)。"""
        from arc.application.execution.artifact_extractor import ArtifactExtractor

        todo = MagicMock()
        todo.project_id = uuid.uuid4()
        project = _make_project_with_model(has_aggregates=True)

        extractor = ArtifactExtractor.__new__(ArtifactExtractor)
        extractor.db = MagicMock()
        extractor._hooks = ArtifactPostProcessHooks(extractor.db, None)

        with patch(
            "arc.infrastructure.repositories.todo.TodoRepository"
        ) as MockTodoRepo, patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.application.baas.domain_model_applier.DomainModelApplier"
        ) as MockApplier, patch(
            "arc.application.baas.service.BaasService"
        ):
            MockTodoRepo.return_value.get_by_id = AsyncMock(return_value=todo)
            MockProjRepo.return_value.get_by_id = AsyncMock(return_value=project)
            mock_applier = MagicMock()
            mock_applier.apply_snapshot = AsyncMock(
                side_effect=Exception("supabase down")
            )
            MockApplier.return_value = mock_applier

            # 不应抛错
            await extractor._hooks.try_provision_baas_after_extract(uuid.uuid4())


class TestHookIntegrationWithExtract:
    """验证 _try_extract_domain_model 成功后调用 BaaS hook。"""

    @pytest.mark.asyncio
    async def test_extract_success_triggers_baas_hook(self):
        """领域模型提取 updated=True → 调 BaaS hook (与 review hook 并列)。"""
        from arc.application.execution.artifact_extractor import ArtifactExtractor

        extractor = ArtifactExtractor.__new__(ArtifactExtractor)
        extractor.db = MagicMock()
        extractor._hooks = ArtifactPostProcessHooks(extractor.db, None)

        with patch(
            "arc.application.execution.domain_model_extractor.DomainModelExtractor"
        ) as MockExtractor, patch.object(
            extractor._hooks, "try_review_after_extract", new=AsyncMock()
        ) as mock_review, patch.object(
            extractor._hooks, "try_provision_baas_after_extract", new=AsyncMock()
        ) as mock_baas:
            mock_extractor_instance = MagicMock()
            mock_extractor_instance.extract_and_merge = AsyncMock(return_value=True)
            MockExtractor.return_value = mock_extractor_instance

            await extractor._hooks.try_extract_domain_model(uuid.uuid4(), {})

            mock_review.assert_awaited_once()
            mock_baas.assert_awaited_once()
