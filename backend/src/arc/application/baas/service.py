"""BaaS 编排服务 (v5.6.0 T7)。

编排逻辑:
- provision: 创建/复用 BaasInstance → 调 SchemaProvisioner → 激活
- apply_model: 取 BaasInstance → 生成并执行 table/policy SQL → 记录 model_version
- introspect: 委托 SchemaProvisioner 读元模型表

不包含 DomainModelSnapshot→BaasSchema 的转换 (那是 DomainModelApplier T8 的职责)。
本服务接收已构建的 BaasSchema。
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.baas.entity import BaasInstance
from arc.domain.baas.errors import SchemaApplyError
from arc.domain.baas.value_objects import BaasSchema, BaasStatus
from arc.domain.errors import DomainError
from arc.infrastructure.baas.rls_generator import generate_policy_sql
from arc.infrastructure.baas.schema_provisioner import SchemaProvisioner
from arc.infrastructure.baas.sql_generator import generate_table_sql
from arc.infrastructure.baas.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class BaasService:
    """编排 BaaS provision + model apply + introspect。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._client = SupabaseClient()
        self._provisioner = SchemaProvisioner(self._client)
        # BaasRepository 由 infrastructure 注入或延迟创建
        from arc.infrastructure.repositories.baas import BaasRepository

        self._baas_repo = BaasRepository(db)

    async def provision(
        self,
        *,
        project_id: uuid.UUID,
        schema_name: str,
        supabase_url: str,
    ) -> BaasInstance:
        """provision Supabase schema (幂等)。

        已有 ACTIVE 实例则直接返回, 不重复 provision。
        """
        # schema 名前置校验 (避免无谓 DB 查询 + 明确错误)
        SupabaseClient._assert_valid_schema_name(schema_name)

        existing = await self._baas_repo.get_by_project(project_id)
        if existing is not None:
            logger.info("provision: project %s 已有 instance, 跳过", project_id)
            return existing

        instance = BaasInstance(
            project_id=project_id,
            schema_name=schema_name,
            supabase_url=supabase_url,
            status=BaasStatus.PROVISIONING,
        )
        instance = await self._baas_repo.create(instance)

        # 真实 provision: CREATE SCHEMA + 元模型表
        await self._provisioner.provision(schema_name)

        instance.activate()
        return await self._baas_repo.update(instance)

    async def apply_model(
        self,
        *,
        project_id: uuid.UUID,
        schema: BaasSchema,
        model_version: int,
    ) -> BaasInstance:
        """应用 BaasSchema 到 Supabase (建表 + RLS 策略)。

        依赖实体状态机: 仅 ACTIVE 可执行, model_version 单调递增。
        """
        instance = await self._baas_repo.get_by_project(project_id)
        if instance is None:
            raise DomainError(
                f"项目 {project_id} 未 provision BaaS, 无法 apply model"
            )

        # 实体状态机校验 (active + 版本单调递增), 失败抛 DomainError
        instance.apply_model(model_version)

        try:
            # 逐表生成并执行 DDL
            for table in schema.tables:
                sql = generate_table_sql(table, schema=schema.schema_name)
                await self._client.execute(sql, schema=schema.schema_name)

            # RLS 策略
            for policy in schema.policies:
                sql = generate_policy_sql(policy, schema=schema.schema_name)
                await self._client.execute(sql, schema=schema.schema_name)
        except Exception as e:
            # SQL 执行失败包装为领域错误, 但 model_version 不回退 (已部分执行)
            raise SchemaApplyError(
                f"apply model v{model_version} 到 schema {schema.schema_name} 失败: {e}"
            ) from e

        logger.info(
            "apply_model: schema=%s version=%d tables=%d policies=%d",
            schema.schema_name, model_version,
            len(schema.tables), len(schema.policies),
        )
        return await self._baas_repo.update(instance)

    async def introspect(self, project_id: uuid.UUID) -> dict:
        """读取项目 Supabase schema 的领域结构概况。"""
        instance = await self._baas_repo.get_by_project(project_id)
        if instance is None:
            return {"schema": None, "exists": False}
        return await self._provisioner.introspect(instance.schema_name)
