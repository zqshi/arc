"""TemplateService 单元测试 — 编辑 + 状态转换 (CRUD service)。"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.template.service import TemplateService
from arc.domain.errors import ConflictError, NotFoundError
from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import TemplateCategory, TemplateStatus


def _make_template(status: TemplateStatus = TemplateStatus.DRAFT) -> DomainTemplate:
    return DomainTemplate(
        title="t",
        description="d",
        category=TemplateCategory.CRUD_APP,
        source_user_id=uuid.uuid4(),
        status=status,
    )


def _make_svc(template: DomainTemplate | None):
    db = MagicMock()
    svc = TemplateService.__new__(TemplateService)
    svc.db = db
    svc.repo = MagicMock()
    svc.repo.get_by_id = AsyncMock(return_value=template)
    svc.repo.update = AsyncMock(side_effect=lambda t: t)
    return svc


class TestTemplateServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_draft_applies_and_persists(self):
        template = _make_template(status=TemplateStatus.DRAFT)
        svc = _make_svc(template)
        result = await svc.update(template.id, {"title": "new", "tags": ["a", "b"]})
        assert result.title == "new"
        assert result.tags == ["a", "b"]
        svc.repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_non_draft_raises_conflict(self):
        template = _make_template(status=TemplateStatus.CONFIRMED)
        svc = _make_svc(template)
        with pytest.raises(ConflictError):
            await svc.update(template.id, {"title": "x"})
        svc.repo.update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_not_found_raises(self):
        svc = _make_svc(None)
        with pytest.raises(NotFoundError):
            await svc.update(uuid.uuid4(), {"title": "x"})


class TestTemplateServiceStateTransitions:
    @pytest.mark.asyncio
    async def test_confirm_transitions_to_confirmed(self):
        template = _make_template(status=TemplateStatus.DRAFT)
        svc = _make_svc(template)
        result = await svc.confirm(template.id)
        assert result.status == TemplateStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_publish_transitions_to_published(self):
        template = _make_template(status=TemplateStatus.CONFIRMED)
        svc = _make_svc(template)
        result = await svc.publish(template.id)
        assert result.status == TemplateStatus.PUBLISHED

    @pytest.mark.asyncio
    async def test_deprecate_transitions_to_deprecated(self):
        template = _make_template(status=TemplateStatus.PUBLISHED)
        svc = _make_svc(template)
        result = await svc.deprecate(template.id)
        assert result.status == TemplateStatus.DEPRECATED

    @pytest.mark.asyncio
    async def test_state_transition_not_found_raises(self):
        svc = _make_svc(None)
        with pytest.raises(NotFoundError):
            await svc.confirm(uuid.uuid4())


class TestTemplateServiceApplyUpdates:
    def test_maps_all_fields(self):
        template = _make_template()
        TemplateService._apply_updates(template, {
            "title": "new title",
            "description": "new desc",
            "category": "workflow",
            "tags": ["x", "y"],
        })
        assert template.title == "new title"
        assert template.description == "new desc"
        assert template.category == TemplateCategory.WORKFLOW
        assert template.tags == ["x", "y"]

    def test_skips_none_fields(self):
        template = _make_template()
        original_title = template.title
        TemplateService._apply_updates(template, {"title": None, "description": "new"})
        assert template.title == original_title
        assert template.description == "new"
