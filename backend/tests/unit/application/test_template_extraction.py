"""Tests for TemplateExtractionService (v5.7.0 T4).

从具体项目 BaasSchema 泛化提取可复用 DomainTemplate。
结构泛化是纯逻辑 (可测), LLM 标题/描述/分类封装为可选步骤。
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.domain.baas.value_objects import (
    ActionDef,
    BaasSchema,
    ColumnDef,
    RlsPolicy,
    StateTransition,
    TableDef,
)
from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateStatus,
)


def _make_concrete_schema() -> BaasSchema:
    """具体项目的 BaasSchema (含项目特定表名/字段名)。"""
    return BaasSchema(
        schema_name="arc_shop123",
        tables=[
            TableDef(name="orders", columns=[
                ColumnDef(name="id", type="uuid", is_primary=True, nullable=False),
                ColumnDef(name="user_id", type="uuid", nullable=False),
                ColumnDef(name="status", type="text", nullable=False),
                ColumnDef(name="total_amount", type="numeric(10,2)"),
            ], has_rls=True, has_state_machine=True, state_field="status"),
            TableDef(name="order_items", columns=[
                ColumnDef(name="id", type="uuid", is_primary=True, nullable=False),
                ColumnDef(name="order_id", type="uuid", references="orders(id)", nullable=False),
                ColumnDef(name="product_name", type="text"),
            ], has_rls=True),
        ],
        policies=[
            RlsPolicy(table_name="orders", operation="SELECT", role="authenticated",
                      using_expr="auth.uid() = user_id"),
            RlsPolicy(table_name="order_items", operation="INSERT", role="authenticated",
                      check_expr="auth.uid() = user_id"),
        ],
        transitions=[
            StateTransition(entity="orders", from_state="pending", to_state="paid",
                            action_name="pay", guard="amount > 0"),
            StateTransition(entity="orders", from_state="paid", to_state="shipped",
                            action_name="ship", guard="true"),
        ],
        actions=[
            ActionDef(name="pay_order", entity="orders", transition=None,
                      preconditions=[], effects=[]),
        ],
    )


class TestExtractStructure:
    def test_generalizes_table_names_to_placeholders(self):
        """具体表名 → 占位符 (保留结构, 去项目特定标识)。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        schema = _make_concrete_schema()
        template_schema = TemplateExtractionService.extract_structure(schema)

        # schema_template 不含原表名
        table_names = [t["name"] for t in template_schema["tables"]]
        assert "orders" not in table_names  # 泛化为占位符
        assert "order_items" not in table_names
        # 但表数量保留
        assert len(template_schema["tables"]) == 2

    def test_preserves_column_types_and_structure(self):
        """列类型和结构模式保留 (uuid/text/numeric, 主键/外键)。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        schema = _make_concrete_schema()
        template_schema = TemplateExtractionService.extract_structure(schema)

        order_table = template_schema["tables"][0]
        col_types = {c["name"]: c["type"] for c in order_table["columns"]}
        assert col_types["id"] == "uuid"
        assert col_types["status"] == "text"
        assert col_types["total_amount"] == "numeric(10,2)"

    def test_detects_entity_patterns(self):
        """识别实体模式 (如 Order-Item 主从关系)。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        schema = _make_concrete_schema()
        patterns = TemplateExtractionService.detect_entity_patterns(schema)

        assert len(patterns) > 0
        # 有外键关系 → 识别出主从模式
        assert any("master-detail" in p.lower() or "主从" in p for p in patterns)

    def test_detects_state_machine_pattern(self):
        """有状态机的表 → 识别状态机模式。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        schema = _make_concrete_schema()
        patterns = TemplateExtractionService.detect_state_machine_patterns(schema)

        assert len(patterns) > 0
        # 状态跃迁模式 (pending→paid→shipped 泛化为 N态链式)
        assert any("chain" in p.lower() or "链" in p for p in patterns)

    def test_detects_permission_patterns(self):
        """RLS 策略 → 识别权限模式 (owner-based)。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        schema = _make_concrete_schema()
        patterns = TemplateExtractionService.detect_permission_patterns(schema)

        assert any("owner-based" in p for p in patterns)  # auth.uid() = user_id

    def test_infers_category_ecommerce(self):
        """含 order + amount + 状态机 → 识别为 ecommerce 类。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        schema = _make_concrete_schema()
        category = TemplateExtractionService.infer_category(schema)
        assert category == TemplateCategory.ECOMMERCE

    def test_infers_category_crud(self):
        """简单 user-content 表 (无电商/社交特征) → crud_app。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        schema = BaasSchema(
            schema_name="arc_blog",
            tables=[
                TableDef(name="posts", columns=[
                    ColumnDef(name="id", type="uuid", is_primary=True, nullable=False),
                    ColumnDef(name="user_id", type="uuid", nullable=False),
                    ColumnDef(name="title", type="text"),
                    ColumnDef(name="content", type="text"),
                ], has_rls=True),
                TableDef(name="categories", columns=[
                    ColumnDef(name="id", type="uuid", is_primary=True, nullable=False),
                    ColumnDef(name="name", type="text"),
                ], has_rls=True),
            ],
            policies=[
                RlsPolicy(table_name="posts", operation="SELECT", role="authenticated",
                          using_expr="auth.uid() = user_id"),
            ],
            transitions=[], actions=[],
        )
        category = TemplateExtractionService.infer_category(schema)
        assert category == TemplateCategory.CRUD_APP


class TestExtractTemplate:
    @pytest.mark.asyncio
    async def test_extract_creates_draft_template(self):
        """extract_template: BaasSchema → DomainTemplate (draft, 含泛化内容)。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        schema = _make_concrete_schema()
        user_id = uuid.uuid4()
        project_id = uuid.uuid4()
        version_id = uuid.uuid4()

        svc = TemplateExtractionService.__new__(TemplateExtractionService)
        # LLM 标题生成 mock (避免真实调用)
        svc._generate_title_desc = AsyncMock(return_value=(
            "电商订单模板", "含订单/订单项/支付状态机的电商应用骨架"
        ))

        template = await svc.extract_template(
            schema=schema,
            source_user_id=user_id,
            source_project_id=project_id,
            source_version_id=version_id,
        )

        assert template.status == TemplateStatus.DRAFT
        assert template.title == "电商订单模板"
        assert template.source_project_id == project_id
        assert template.source_version_id == version_id
        assert template.source_user_id == user_id
        assert template.category == TemplateCategory.ECOMMERCE
        assert len(template.schema_template["tables"]) == 2
        assert len(template.entity_patterns) > 0
        assert len(template.permission_patterns) > 0

    @pytest.mark.asyncio
    async def test_extract_uses_fallback_title_when_llm_fails(self):
        """LLM 失败时用结构化 fallback 标题 (不阻断)。"""
        from arc.application.template.extraction_service import (
            TemplateExtractionService,
        )

        schema = _make_concrete_schema()
        svc = TemplateExtractionService.__new__(TemplateExtractionService)
        svc._generate_title_desc = AsyncMock(side_effect=Exception("LLM down"))

        template = await svc.extract_template(
            schema=schema,
            source_user_id=uuid.uuid4(),
        )

        # fallback 标题 (含分类)
        assert "电商" in template.title or "ecommerce" in template.title.lower()
