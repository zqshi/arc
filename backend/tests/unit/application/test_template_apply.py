"""Tests for TemplateApplyService (v5.7.0 T6).

模板适配: 选中模板 + 新需求 → LLM 生成具体 BaasSchema → apply 到 Supabase。
mock LLM + BaasService, 验证编排逻辑。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.domain.baas.value_objects import BaasSchema
from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateStatus,
)


def _make_template() -> DomainTemplate:
    return DomainTemplate(
        title="电商模板",
        description="电商骨架",
        category=TemplateCategory.ECOMMERCE,
        source_user_id=uuid.uuid4(),
        status=TemplateStatus.PUBLISHED,
        schema_template={
            "tables": [
                {
                    "name": "table_1",
                    "original_role": "order-main",
                    "columns": [
                        {"name": "id", "type": "uuid", "is_primary": True},
                        {"name": "status", "type": "text"},
                    ],
                    "has_rls": True,
                    "has_state_machine": True,
                },
            ]
        },
        entity_patterns=["master-detail (主从关系)"],
    )


class TestAdaptTemplate:
    @pytest.mark.asyncio
    async def test_adapt_returns_concrete_baas_schema(self):
        """模板 + 需求 → LLM 适配 → 具体项目 BaasSchema。"""
        from arc.application.template.apply_service import TemplateApplyService

        template = _make_template()
        project_id = uuid.uuid4()

        svc = TemplateApplyService.__new__(TemplateApplyService)
        svc._adapt_with_llm = AsyncMock(return_value={
            "tables": [
                {
                    "name": "orders",
                    "columns": [
                        {"name": "id", "type": "uuid", "is_primary": True, "nullable": False},
                        {"name": "status", "type": "text", "nullable": False},
                    ],
                    "has_rls": True,
                    "has_state_machine": True,
                    "state_field": "status",
                },
            ],
            "policies": [],
            "transitions": [],
            "actions": [],
        })

        schema = await svc.adapt_template(
            template=template,
            requirement="电商订单系统",
            project_id=project_id,
        )

        assert isinstance(schema, BaasSchema)
        assert schema.schema_name.startswith("arc_")
        assert len(schema.tables) == 1
        assert schema.tables[0].name == "orders"
        assert schema.tables[0].has_state_machine is True

    @pytest.mark.asyncio
    async def test_adapt_llm_fails_raises(self):
        """LLM 适配失败应抛错 (无法生成有效 schema, 不 fallback 到空 schema)。"""
        from arc.application.template.apply_service import TemplateApplyService
        from arc.domain.baas.errors import SchemaApplyError

        template = _make_template()
        svc = TemplateApplyService.__new__(TemplateApplyService)
        svc._adapt_with_llm = AsyncMock(side_effect=Exception("LLM down"))

        with pytest.raises(SchemaApplyError, match="适配失败"):
            await svc.adapt_template(
                template=template,
                requirement="query",
                project_id=uuid.uuid4(),
            )

    @pytest.mark.asyncio
    async def test_adapt_schema_name_derived_from_project(self):
        """适配出的 BaasSchema 用目标 project_id 派生 schema_name。"""
        from arc.application.template.apply_service import TemplateApplyService

        template = _make_template()
        project_id = uuid.UUID("abcdef12-0000-0000-0000-000000000000")

        svc = TemplateApplyService.__new__(TemplateApplyService)
        svc._adapt_with_llm = AsyncMock(return_value={
            "tables": [], "policies": [], "transitions": [], "actions": [],
        })

        schema = await svc.adapt_template(
            template=template, requirement="q", project_id=project_id
        )
        assert schema.schema_name == "arc_abcdef12"


class TestApplyTemplate:
    @pytest.mark.asyncio
    async def test_apply_records_usage_on_success(self):
        """apply 成功 → 记录模板使用 (success=True)。"""
        from arc.application.template.apply_service import TemplateApplyService

        template = _make_template()
        template.usage_count = 0
        project_id = uuid.uuid4()

        baas_service = MagicMock()
        baas_service.provision = AsyncMock()
        baas_service.apply_model = AsyncMock()
        template_repo = MagicMock()
        template_repo.update = AsyncMock(side_effect=lambda t: t)

        svc = TemplateApplyService.__new__(TemplateApplyService)
        svc._baas_service = baas_service
        svc._template_repo = template_repo
        svc._adapt_with_llm = AsyncMock(return_value={
            "tables": [{"name": "t", "columns": [
                {"name": "id", "type": "uuid", "is_primary": True, "nullable": False}
            ], "has_rls": True}],
            "policies": [], "transitions": [], "actions": [],
        })

        await svc.apply_template(
            template=template,
            requirement="query",
            project_id=project_id,
            supabase_url="http://localhost:54321",
            model_version=1,
        )

        baas_service.apply_model.assert_awaited_once()
        # 模板使用计数 +1
        assert template.usage_count == 1
        assert template.success_count == 1
        template_repo.update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_apply_records_failure_on_baas_error(self):
        """apply 失败 (BaasService 抛错) → 记录 success=False 但不吞错。"""
        from arc.application.template.apply_service import TemplateApplyService
        from arc.domain.baas.errors import SchemaApplyError

        template = _make_template()
        baas_service = MagicMock()
        baas_service.provision = AsyncMock()
        baas_service.apply_model = AsyncMock(side_effect=SchemaApplyError("apply failed"))
        template_repo = MagicMock()
        template_repo.update = AsyncMock(side_effect=lambda t: t)

        svc = TemplateApplyService.__new__(TemplateApplyService)
        svc._baas_service = baas_service
        svc._template_repo = template_repo
        svc._adapt_with_llm = AsyncMock(return_value={
            "tables": [], "policies": [], "transitions": [], "actions": [],
        })

        with pytest.raises(SchemaApplyError):
            await svc.apply_template(
                template=template,
                requirement="q",
                project_id=uuid.uuid4(),
                supabase_url="http://localhost:54321",
                model_version=1,
            )

        # 失败也记录使用 (success=False)
        assert template.usage_count == 1
        assert template.success_count == 0
