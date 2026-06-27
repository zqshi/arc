"""Tests for release hook — 模板提取 (v5.7.0 T7).

版本发布后自动从项目领域模型提取模板草稿。
mock ExtractionService + repos, 验证 hook 编排。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateStatus,
)


def _make_project(*, has_model: bool = True, user_id=None):
    project = MagicMock()
    project.id = uuid.uuid4()
    project.user_id = user_id or uuid.uuid4()
    project.domain_model = (
        {"version": 2, "aggregates": [{"name": "Order", "fields": ["id", "status"]}]}
        if has_model
        else None
    )
    return project


class TestExtractTemplateAfterRelease:
    @pytest.mark.asyncio
    async def test_extract_triggered_when_model_has_aggregates(self):
        """项目有领域模型聚合 → 触发模板提取并保存 draft。"""
        from arc.application.project.service import VersionService

        project = _make_project(has_model=True)

        svc = VersionService.__new__(VersionService)
        svc.db = MagicMock()

        template = DomainTemplate(
            title="提取的模板",
            description="desc",
            category=TemplateCategory.ECOMMERCE,
            source_user_id=project.user_id,
            status=TemplateStatus.DRAFT,
        )

        with patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.application.template.extraction_service.TemplateExtractionService"
        ) as MockExtraction, patch(
            "arc.infrastructure.repositories.template.TemplateRepository"
        ) as MockTemplateRepo, patch(
            "arc.application.baas.domain_model_applier.DomainModelApplier"
        ):
            MockProjRepo.return_value.get_by_id = AsyncMock(return_value=project)

            mock_extraction = MagicMock()
            mock_extraction.extract_template = AsyncMock(return_value=template)
            MockExtraction.return_value = mock_extraction

            mock_template_repo = MagicMock()
            mock_template_repo.create = AsyncMock(side_effect=lambda t: t)
            MockTemplateRepo.return_value = mock_template_repo

            await svc._extract_template_after_release(
                project_id=project.id, version_id=uuid.uuid4()
            )

            mock_extraction.extract_template.assert_awaited_once()
            mock_template_repo.create.assert_awaited_once()
            # 保存的是 draft 模板
            saved = mock_template_repo.create.call_args.args[0]
            assert saved.status == TemplateStatus.DRAFT
            # extract_template 被以正确 project_id/user_id 调用
            call_kwargs = mock_extraction.extract_template.call_args.kwargs
            assert call_kwargs["source_project_id"] == project.id
            assert call_kwargs["source_user_id"] == project.user_id
            assert call_kwargs["source_version_id"] is not None

    @pytest.mark.asyncio
    async def test_extract_skipped_when_no_domain_model(self):
        """项目无领域模型 → 跳过提取。"""
        from arc.application.project.service import VersionService

        project = _make_project(has_model=False)
        svc = VersionService.__new__(VersionService)
        svc.db = MagicMock()

        with patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.application.template.extraction_service.TemplateExtractionService"
        ) as MockExtraction:
            MockProjRepo.return_value.get_by_id = AsyncMock(return_value=project)
            mock_extraction = MagicMock()
            mock_extraction.extract_template = AsyncMock()
            MockExtraction.return_value = mock_extraction

            await svc._extract_template_after_release(
                project_id=project.id, version_id=uuid.uuid4()
            )

            mock_extraction.extract_template.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_failure_does_not_raise(self):
        """提取失败不阻断 release (仅 warning)。"""
        from arc.application.project.service import VersionService

        project = _make_project(has_model=True)
        svc = VersionService.__new__(VersionService)
        svc.db = MagicMock()

        with patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.application.template.extraction_service.TemplateExtractionService"
        ) as MockExtraction:
            MockProjRepo.return_value.get_by_id = AsyncMock(return_value=project)
            mock_extraction = MagicMock()
            mock_extraction.extract_template = AsyncMock(
                side_effect=Exception("extraction failed")
            )
            MockExtraction.return_value = mock_extraction

            # 不应抛错
            await svc._extract_template_after_release(
                project_id=project.id, version_id=uuid.uuid4()
            )

    @pytest.mark.asyncio
    async def test_extract_skipped_when_project_not_found(self):
        from arc.application.project.service import VersionService

        svc = VersionService.__new__(VersionService)
        svc.db = MagicMock()

        with patch(
            "arc.infrastructure.repositories.project.ProjectRepository"
        ) as MockProjRepo, patch(
            "arc.application.template.extraction_service.TemplateExtractionService"
        ) as MockExtraction:
            MockProjRepo.return_value.get_by_id = AsyncMock(return_value=None)
            mock_extraction = MagicMock()
            MockExtraction.return_value = mock_extraction

            await svc._extract_template_after_release(
                project_id=uuid.uuid4(), version_id=uuid.uuid4()
            )

            mock_extraction.extract_template.assert_not_called()
