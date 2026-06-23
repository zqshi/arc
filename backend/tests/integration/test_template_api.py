"""模板 API 集成测试 (v5.7.0 T9)。"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateStatus,
)


async def _create_template_via_db(db_session, *, title="测试模板", status=TemplateStatus.DRAFT, user_id=None):
    """直接 DB 插入模板 (绕过 API, 构造测试数据)。"""
    from arc.infrastructure.repositories.template import TemplateRepository

    template = DomainTemplate(
        title=title,
        description="描述",
        category=TemplateCategory.CRUD_APP,
        source_user_id=user_id or uuid.UUID("00000000-0000-0000-0000-000000000001"),
        status=status,
        entity_patterns=["User-Content"],
    )
    return await TemplateRepository(db_session).create(template)


@pytest.fixture
async def cleanup(db_session):
    yield
    await db_session.execute(text("DELETE FROM domain_templates"))
    await db_session.commit()


class TestTemplateList:
    @pytest.mark.asyncio
    async def test_list_returns_user_templates(self, client: AsyncClient, db_session, cleanup):
        await _create_template_via_db(db_session, title="T1")
        resp = await client.get("/api/templates")
        assert resp.status_code == 200
        assert any(t["title"] == "T1" for t in resp.json())

    @pytest.mark.asyncio
    async def test_list_supports_pagination(self, client: AsyncClient, db_session, cleanup):
        for i in range(3):
            await _create_template_via_db(db_session, title=f"T{i}")
        resp = await client.get("/api/templates", params={"skip": 0, "limit": 2})
        assert len(resp.json()) <= 2


class TestTemplateGet:
    @pytest.mark.asyncio
    async def test_get_existing(self, client: AsyncClient, db_session, cleanup):
        t = await _create_template_via_db(db_session, title="单个")
        resp = await client.get(f"/api/templates/{t.id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "单个"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get(f"/api/templates/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestTemplateLifecycle:
    @pytest.mark.asyncio
    async def test_confirm_draft(self, client: AsyncClient, db_session, cleanup):
        t = await _create_template_via_db(db_session)
        resp = await client.post(f"/api/templates/{t.id}/confirm")
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

    @pytest.mark.asyncio
    async def test_publish_confirmed(self, client: AsyncClient, db_session, cleanup):
        t = await _create_template_via_db(db_session, status=TemplateStatus.CONFIRMED)
        resp = await client.post(f"/api/templates/{t.id}/publish")
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"

    @pytest.mark.asyncio
    async def test_publish_draft_raises_409(self, client: AsyncClient, db_session, cleanup):
        """draft 未确认不可直接 publish。"""
        t = await _create_template_via_db(db_session)
        resp = await client.post(f"/api/templates/{t.id}/publish")
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_deprecate_published(self, client: AsyncClient, db_session, cleanup):
        t = await _create_template_via_db(db_session, status=TemplateStatus.PUBLISHED)
        resp = await client.post(f"/api/templates/{t.id}/deprecate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deprecated"


class TestTemplateUpdate:
    @pytest.mark.asyncio
    async def test_update_draft(self, client: AsyncClient, db_session, cleanup):
        t = await _create_template_via_db(db_session)
        resp = await client.patch(f"/api/templates/{t.id}", json={"title": "改后"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "改后"

    @pytest.mark.asyncio
    async def test_update_non_draft_raises_409(self, client: AsyncClient, db_session, cleanup):
        """非 draft 状态不可编辑。"""
        t = await _create_template_via_db(db_session, status=TemplateStatus.PUBLISHED)
        resp = await client.patch(f"/api/templates/{t.id}", json={"title": "x"})
        assert resp.status_code == 409
