"""模板全链路集成测试 (v5.7.0 T11).

提取 (extraction) → 匹配 (matching) → 套用 (apply) 端到端。
LLM 步骤 mock (标题生成/适配), 结构泛化 + 向量搜索走真实 PG。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text

from arc.domain.baas.value_objects import (
    BaasSchema,
    ColumnDef,
    RlsPolicy,
    TableDef,
)
from arc.domain.template.value_objects import TemplateStatus


def _make_schema() -> BaasSchema:
    return BaasSchema(
        schema_name="arc_chain_test",
        tables=[
            TableDef(name="orders", columns=[
                ColumnDef(name="id", type="uuid", is_primary=True, nullable=False,
                          default="gen_random_uuid()"),
                ColumnDef(name="user_id", type="uuid", nullable=False),
                ColumnDef(name="status", type="text", nullable=False),
            ], has_rls=True, has_state_machine=True, state_field="status"),
        ],
        policies=[
            RlsPolicy(table_name="orders", operation="SELECT", role="authenticated",
                      using_expr="auth.uid() = user_id"),
        ],
        transitions=[], actions=[],
    )


@pytest.fixture
async def cleanup(db_session):
    yield
    await db_session.execute(text("DELETE FROM domain_templates"))
    await db_session.execute(text("DELETE FROM baas_instances WHERE schema_name LIKE 'arc_%'")
                             if False else text("DELETE FROM baas_instances"))
    await db_session.commit()


class TestExtractionToMatchingToApply:
    @pytest.mark.asyncio
    async def test_full_pipeline(self, db_session, cleanup):
        """提取 → confirm → publish → 匹配 → apply 全链路。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )
        from arc.application.template.matching_service import (
            TemplateMatchingService,
        )
        from arc.infrastructure.repositories.template import TemplateRepository

        user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        repo = TemplateRepository(db_session)

        # 1. 提取 (LLM 标题 mock)
        extraction = TemplateExtractionService()
        with patch.object(
            extraction, "_generate_title_desc",
            new=AsyncMock(return_value=("电商订单模板", "含订单状态机的电商骨架")),
        ):
            template = await extraction.extract_template(
                schema=_make_schema(),
                source_user_id=user_id,
                source_project_id=None,  # 集成测试不建真实 project
            )
        await repo.create(template)
        assert template.status == TemplateStatus.DRAFT
        assert template.title == "电商订单模板"

        # 2. confirm → publish
        template.confirm()
        template.publish()
        await repo.update(template)
        assert template.status == TemplateStatus.PUBLISHED

        # 给模板设 embedding (mock, 真实场景 release hook 会调 LLM embed)
        template.embedding = [1.0] * 1536
        await repo.update(template)

        # 3. 匹配 (LLM embed mock, 向量搜索真实)
        matching = TemplateMatchingService(repo)
        with patch(
            "arc.application.ai.resilience.create_resilient_adapter"
        ) as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.embed = AsyncMock(return_value=[0.99] * 1536)
            mock_adapter.close = AsyncMock()
            MockAdapter.return_value = mock_adapter

            results = await matching.search_matching("电商订单系统", limit=5)

        assert len(results) >= 1
        matched, score = results[0]
        assert matched.title == "电商订单模板"
        assert score > 0.5

    @pytest.mark.asyncio
    async def test_extracted_template_has_generalized_structure(self, db_session, cleanup):
        """提取的模板 schema_template 用占位符表名 (去项目特定标识)。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        extraction = TemplateExtractionService()
        with patch.object(
            extraction, "_generate_title_desc",
            new=AsyncMock(return_value=("模板", "描述")),
        ):
            template = await extraction.extract_template(
                schema=_make_schema(),
                source_user_id=uuid.uuid4(),
            )

        # schema_template 表名是占位符, 不是 "orders"
        table_names = [t["name"] for t in template.schema_template["tables"]]
        assert "orders" not in table_names
        assert all(name.startswith("table_") for name in table_names)
        # 但列结构保留
        cols = template.schema_template["tables"][0]["columns"]
        col_types = {c["name"]: c["type"] for c in cols}
        assert col_types["id"] == "uuid"
        assert col_types["status"] == "text"

    @pytest.mark.asyncio
    async def test_apply_records_usage(self, db_session, cleanup):
        """套用成功后模板 usage_count +1, success_count +1。"""
        from arc.application.template.apply_service import TemplateApplyService
        from arc.infrastructure.repositories.template import TemplateRepository

        repo = TemplateRepository(db_session)
        from arc.domain.template.entity import DomainTemplate
        from arc.domain.template.value_objects import TemplateCategory

        template = DomainTemplate(
            title="电商模板",
            description="desc",
            category=TemplateCategory.ECOMMERCE,
            source_user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            status=TemplateStatus.PUBLISHED,
            schema_template={"tables": []},
        )
        await repo.create(template)

        baas_service = MagicMock()
        baas_service.provision = AsyncMock()
        baas_service.apply_model = AsyncMock()

        svc = TemplateApplyService(baas_service, repo)
        # LLM 适配 mock
        with patch.object(
            svc, "_adapt_with_llm",
            new=AsyncMock(return_value={
                "tables": [], "policies": [], "transitions": [], "actions": [],
            }),
        ):
            await svc.apply_template(
                template=template,
                requirement="query",
                project_id=uuid.uuid4(),
                supabase_url="http://localhost:54321",
                model_version=1,
            )

        # 重新读, 验证使用计数持久化
        refreshed = await repo.get_by_id(template.id)
        assert refreshed.usage_count == 1
        assert refreshed.success_count == 1
