"""Tests for ARCHITECTURE 阶段 BaaS provision hook (v5.6.0 T11).

领域模型提取成功后自动触发 BaaS provision。v6.24 治理: hook 改调
DomainModelService.provision_baas 统一入口 (消除与 pipeline 路径的 apply_snapshot
编排重复), 测试 mock service.provision_baas 而非底层 DomainModelApplier。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.execution.artifact_post_process import ArtifactPostProcessHooks


class TestTryProvisionBaasAfterExtract:
    @pytest.mark.asyncio
    async def test_provision_triggered_when_model_has_aggregates(self):
        """provision_baas 返回 provisioned=True → success, 调 service.provision_baas。"""
        from arc.application.execution.artifact_extractor import ArtifactExtractor

        todo = MagicMock()
        todo.project_id = uuid.uuid4()

        extractor = ArtifactExtractor.__new__(ArtifactExtractor)
        extractor.db = MagicMock()
        extractor._hooks = ArtifactPostProcessHooks(extractor.db, None)

        with patch(
            "arc.infrastructure.repositories.todo.TodoRepository"
        ) as MockTodoRepo, patch(
            "arc.application.project.domain_model_service.DomainModelService"
        ) as MockSvc:
            MockTodoRepo.return_value.get_by_id = AsyncMock(return_value=todo)
            mock_svc = MagicMock()
            mock_svc.provision_baas = AsyncMock(
                return_value={"provisioned": True, "schema_name": "arc_test"}
            )
            MockSvc.return_value = mock_svc

            await extractor._hooks.try_provision_baas_after_extract(uuid.uuid4())

            mock_svc.provision_baas.assert_awaited_once()
            assert mock_svc.provision_baas.call_args.args[0] == todo.project_id

    @pytest.mark.asyncio
    async def test_provision_skipped_when_no_aggregates(self):
        """provision_baas 返回 provisioned=False (reason_code=no_aggregates) → skip 不阻断。"""
        from arc.application.execution.artifact_extractor import ArtifactExtractor

        todo = MagicMock()
        todo.project_id = uuid.uuid4()

        extractor = ArtifactExtractor.__new__(ArtifactExtractor)
        extractor.db = MagicMock()
        extractor._hooks = ArtifactPostProcessHooks(extractor.db, None)

        with patch(
            "arc.infrastructure.repositories.todo.TodoRepository"
        ) as MockTodoRepo, patch(
            "arc.application.project.domain_model_service.DomainModelService"
        ) as MockSvc:
            MockTodoRepo.return_value.get_by_id = AsyncMock(return_value=todo)
            mock_svc = MagicMock()
            mock_svc.provision_baas = AsyncMock(
                return_value={
                    "provisioned": False,
                    "reason": "领域模型无聚合",
                    "reason_code": "no_aggregates",
                }
            )
            MockSvc.return_value = mock_svc

            # 不应抛错 (skip 路径)
            await extractor._hooks.try_provision_baas_after_extract(uuid.uuid4())

            mock_svc.provision_baas.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_provision_skipped_when_no_project(self):
        """todo 无 project_id → skip_no_project, 不调 provision_baas。"""
        from arc.application.execution.artifact_extractor import ArtifactExtractor

        todo = MagicMock()
        todo.project_id = None

        extractor = ArtifactExtractor.__new__(ArtifactExtractor)
        extractor.db = MagicMock()
        extractor._hooks = ArtifactPostProcessHooks(extractor.db, None)

        with patch(
            "arc.infrastructure.repositories.todo.TodoRepository"
        ) as MockTodoRepo, patch(
            "arc.application.project.domain_model_service.DomainModelService"
        ) as MockSvc:
            MockTodoRepo.return_value.get_by_id = AsyncMock(return_value=todo)
            mock_svc = MagicMock()
            mock_svc.provision_baas = AsyncMock()
            MockSvc.return_value = mock_svc

            await extractor._hooks.try_provision_baas_after_extract(uuid.uuid4())

            mock_svc.provision_baas.assert_not_called()

    @pytest.mark.asyncio
    async def test_provision_failure_does_not_raise(self):
        """provision_baas 抛异常 → 记 fail metrics, 不阻断主流程。"""
        from arc.application.execution.artifact_extractor import ArtifactExtractor

        todo = MagicMock()
        todo.project_id = uuid.uuid4()

        extractor = ArtifactExtractor.__new__(ArtifactExtractor)
        extractor.db = MagicMock()
        extractor._hooks = ArtifactPostProcessHooks(extractor.db, None)

        with patch(
            "arc.infrastructure.repositories.todo.TodoRepository"
        ) as MockTodoRepo, patch(
            "arc.application.project.domain_model_service.DomainModelService"
        ) as MockSvc:
            MockTodoRepo.return_value.get_by_id = AsyncMock(return_value=todo)
            mock_svc = MagicMock()
            mock_svc.provision_baas = AsyncMock(side_effect=Exception("supabase down"))
            MockSvc.return_value = mock_svc

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
