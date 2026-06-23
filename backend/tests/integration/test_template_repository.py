"""TemplateRepository 集成测试 (v5.7.0 T3).

真实 PG: create/get/list/update + embedding 向量搜索。
"""
from __future__ import annotations

import uuid

import pytest

from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateScope,
    TemplateStatus,
)


def _make_template(
    *, title: str = "CRUD 模板", status: TemplateStatus = TemplateStatus.DRAFT
) -> DomainTemplate:
    return DomainTemplate(
        title=title,
        description="用户-内容-分类",
        category=TemplateCategory.CRUD_APP,
        source_user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        status=status,
        entity_patterns=["User-Content-Category"],
    )


@pytest.fixture
async def cleanup(db_session):
    """每个测试后清理 domain_templates 表。"""
    yield
    from sqlalchemy import text

    await db_session.execute(text("DELETE FROM domain_templates"))
    await db_session.commit()


class TestTemplateCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get(self, db_session, cleanup):
        from arc.infrastructure.repositories.template import TemplateRepository

        repo = TemplateRepository(db_session)
        template = _make_template()
        created = await repo.create(template)

        assert created.id == template.id
        fetched = await repo.get_by_id(template.id)
        assert fetched is not None
        assert fetched.title == "CRUD 模板"
        assert fetched.category == TemplateCategory.CRUD_APP
        assert fetched.entity_patterns == ["User-Content-Category"]

    @pytest.mark.asyncio
    async def test_get_not_found(self, db_session, cleanup):
        from arc.infrastructure.repositories.template import TemplateRepository

        repo = TemplateRepository(db_session)
        fetched = await repo.get_by_id(uuid.uuid4())
        assert fetched is None

    @pytest.mark.asyncio
    async def test_list_by_user(self, db_session, cleanup):
        from arc.infrastructure.repositories.template import TemplateRepository

        repo = TemplateRepository(db_session)
        user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        await repo.create(_make_template(title="T1"))
        await repo.create(_make_template(title="T2"))

        templates = await repo.list_by_user(user_id)
        assert len(templates) == 2

    @pytest.mark.asyncio
    async def test_list_published_excludes_draft(self, db_session, cleanup):
        from arc.infrastructure.repositories.template import TemplateRepository

        repo = TemplateRepository(db_session)
        await repo.create(_make_template(title="draft", status=TemplateStatus.DRAFT))
        pub = _make_template(title="published", status=TemplateStatus.PUBLISHED)
        pub.confirm  # noqa: 已是 published, 跳过状态机
        await repo.create(pub)

        published = await repo.list_published()
        titles = [t.title for t in published]
        assert "published" in titles
        assert "draft" not in titles

    @pytest.mark.asyncio
    async def test_update_status_and_usage(self, db_session, cleanup):
        from arc.infrastructure.repositories.template import TemplateRepository

        repo = TemplateRepository(db_session)
        template = _make_template()
        await repo.create(template)

        template.confirm()
        template.record_usage(success=True)
        updated = await repo.update(template)

        assert updated.status == TemplateStatus.CONFIRMED
        assert updated.usage_count == 1
        assert updated.success_count == 1


class TestTemplateEmbeddingSearch:
    @pytest.mark.asyncio
    async def test_search_returns_similar(self, db_session, cleanup):
        """向量搜索: 已发布模板按相似度返回。"""
        from arc.infrastructure.repositories.template import TemplateRepository

        repo = TemplateRepository(db_session)
        # 两个已发布模板, 不同方向 embedding
        t1 = _make_template(title="CRUD", status=TemplateStatus.PUBLISHED)
        t1.embedding = [1.0] * 1536
        await repo.create(t1)

        t2 = _make_template(title="Workflow", status=TemplateStatus.PUBLISHED)
        t2.embedding = [0.0] * 1536
        await repo.create(t2)

        # 查询向量接近 t1
        query = [0.99] * 1536
        results = await repo.search_by_embedding(query, limit=5)

        assert len(results) == 2
        top_template, top_sim = results[0]
        assert top_template.title == "CRUD"  # 最相似
        assert top_sim > 0.9

    @pytest.mark.asyncio
    async def test_search_excludes_unpublished(self, db_session, cleanup):
        """未发布模板不参与搜索。"""
        from arc.infrastructure.repositories.template import TemplateRepository

        repo = TemplateRepository(db_session)
        draft = _make_template(title="draft", status=TemplateStatus.DRAFT)
        draft.embedding = [1.0] * 1536
        await repo.create(draft)

        results = await repo.search_by_embedding([1.0] * 1536)
        assert results == []
