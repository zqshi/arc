"""BaaS 触发链路端到端集成测试 (v6.19 续9).

覆盖 test_baas_provision (直接调 BaasService.provision) 未覆盖的触发链路 ——
artifact_extractor.py:111 try_extract_domain_model 的真实子步骤:
  DomainModelExtractor.extract_and_merge(tech_architecture)
    -> 产出 aggregates 入 project.domain_model (DomainModel 升版本)
  ArtifactPostProcessHooks.try_provision_baas_after_extract
    -> BaasService.provision + apply_model -> 真实 pg schema/表/RLS

dev 降级: supabase_db_url="" -> 复用 arc database_url 同库隔离 (arc_{hex} schema)。
cleanup: asyncpg DROP SCHEMA (与 provision 对称持久化, 见 test_baas_provision._cleanup_schema 注)。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from arc.infrastructure.baas.supabase_client import SupabaseClient

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def _cleanup_schema(db_session: AsyncSession, schema_name: str) -> None:
    """asyncpg DROP SCHEMA 持久化 (与 provision 对称, 避免 orphan 泄漏)。"""
    client = SupabaseClient()
    try:
        await client.execute(
            f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE', schema=None
        )
    finally:
        await client.close()
    await db_session.execute(
        text("DELETE FROM baas_instances WHERE schema_name = :name"),
        {"name": schema_name},
    )
    await db_session.commit()


async def _make_project_and_todo(db_session: AsyncSession):
    """直接用 repository 建 project + todo (聚焦触发链路, 不走 HTTP 路由)。"""
    from arc.domain.project.entity import Project
    from arc.domain.project.value_objects import ProjectType
    from arc.domain.todo.entity import Todo
    from arc.infrastructure.repositories.project import ProjectRepository
    from arc.infrastructure.repositories.todo import TodoRepository

    project = Project(name=f"Trigger E2E {uuid.uuid4().hex[:6]}", project_type=ProjectType.STATIC_SITE)
    project = await ProjectRepository(db_session).create(project, user_id=TEST_USER_ID)
    todo = Todo(title="trigger test todo", project_id=project.id)
    todo = await TodoRepository(db_session).create(todo, user_id=TEST_USER_ID)
    await db_session.flush()
    return project, todo


class TestBaasTriggerE2E:
    """触发链路: extract_and_merge -> try_provision_baas_after_extract -> 真建 schema。"""

    @pytest.mark.asyncio
    async def test_extract_provision_creates_real_schema(self, db_session: AsyncSession):
        """tech_architecture 含 data_model.entities -> extract 升版本 -> provision 真建 schema/表/RLS。"""
        from arc.application.execution.artifact_post_process import ArtifactPostProcessHooks
        from arc.application.execution.domain_model_extractor import DomainModelExtractor
        from arc.infrastructure.repositories.project import ProjectRepository

        project, todo = await _make_project_and_todo(db_session)
        schema_name = f"arc_{project.id.hex[:8]}"
        tech_arch = {
            "data_model": {
                "entities": [
                    {"name": "Post", "fields": [{"name": "id"}, {"name": "title"}]},
                ]
            }
        }

        try:
            # --- 触发链路 (artifact_extractor.py:111 真实子步骤) ---
            extractor = DomainModelExtractor(db_session)
            updated = await extractor.extract_and_merge(todo.id, tech_arch)
            assert updated is True, "extract 应产出 aggregates 升版本"

            hooks = ArtifactPostProcessHooks(db_session, tracker_repo=None)
            await hooks.try_provision_baas_after_extract(todo.id)
            await db_session.flush()

            # --- 验证 pg 真实证据 ---
            client = SupabaseClient()
            try:
                # schema 真建
                assert await client.schema_exists(schema_name) is True

                # 业务表 (Post -> posts 复数化) 真建
                table = await client.fetchval(
                    f"SELECT to_regclass('{schema_name}.posts')", schema=schema_name
                )
                assert table is not None

                # RLS 启用 (has_rls=True -> ALTER ENABLE RLS)
                rls = await client.fetchval(
                    "SELECT relrowsecurity FROM pg_class WHERE relname='posts'",
                    schema=schema_name,
                )
                assert rls is True

                # 元模型表 provision 真建
                meta = await client.fetchval(
                    f'SELECT count(*) FROM "{schema_name}"._meta_entities', schema=schema_name
                )
                assert meta == 0  # 空表, 结构存在
            finally:
                await client.close()

            # domain_model 升版本 + aggregates 入库
            proj = await ProjectRepository(db_session).get_by_id(project.id)
            assert proj.domain_model.get("version") == 1
            assert len(proj.domain_model.get("aggregates", [])) == 1
        finally:
            await _cleanup_schema(db_session, schema_name)

    @pytest.mark.asyncio
    async def test_provision_skipped_when_no_entities(self, db_session: AsyncSession):
        """tech_architecture 无 data_model.entities -> extract 返回 False -> provision skip (schema 不建)。

        固化 graceful skip 边界: Agent 若输出无 data_model.entities 的 tech_architecture,
        DomainModelExtractor 不更新模型, try_provision_baas 内部 aggregates 空 skip,
        schema 不建 (用户侧无错误可见, 仅 info 日志) —— 续9 段记录的真实风险。
        """
        from arc.application.execution.artifact_post_process import ArtifactPostProcessHooks
        from arc.application.execution.domain_model_extractor import DomainModelExtractor

        project, todo = await _make_project_and_todo(db_session)
        schema_name = f"arc_{project.id.hex[:8]}"
        tech_arch_no_entities = {"data_model": {"entities": []}}

        try:
            extractor = DomainModelExtractor(db_session)
            updated = await extractor.extract_and_merge(todo.id, tech_arch_no_entities)
            assert updated is False, "无 entities 不应更新模型"

            hooks = ArtifactPostProcessHooks(db_session, tracker_repo=None)
            await hooks.try_provision_baas_after_extract(todo.id)
            await db_session.flush()

            # schema 不应被建 (provision skip)
            client = SupabaseClient()
            try:
                assert await client.schema_exists(schema_name) is False
            finally:
                await client.close()
        finally:
            await _cleanup_schema(db_session, schema_name)
