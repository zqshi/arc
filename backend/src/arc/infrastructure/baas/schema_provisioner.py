"""SchemaProvisioner — Supabase schema 创建 + 元模型初始化 (v5.6.0 T4)。

职责:
- provision(schema): CREATE SCHEMA (若不存在) + 元模型表初始化 (幂等)
- introspect(schema): 读取元模型表, 返回当前领域结构概况 (供 Agent get_domain_model)

不在本层做 DomainModel→表 的 apply (那是 DomainModelApplier T8 的职责)。
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from arc.domain.baas.errors import ProvisionError
from arc.infrastructure.baas.sql_generator import (
    generate_create_schema_sql,
    generate_ensure_auth_uid_sql,
    generate_ensure_roles_sql,
    generate_meta_tables_sql,
)

if TYPE_CHECKING:
    from arc.infrastructure.baas.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class SchemaProvisioner:
    def __init__(self, client: SupabaseClient) -> None:
        self._client = client

    async def provision(self, schema: str) -> None:
        """创建 schema + 元模型表 (幂等, 可重复执行)。"""
        try:
            # v6.24 P0-2: 确保 Supabase 约定角色存在 (RLS policy TO authenticated 依赖)
            await self._client.execute(generate_ensure_roles_sql(), schema=None)
            # v6.24 P0-2: 确保 auth.uid() 可用 (user_id DEFAULT + RLS USING 依赖)
            await self._client.execute(generate_ensure_auth_uid_sql(), schema=None)
            exists = await self._client.schema_exists(schema)
            if not exists:
                await self._client.execute(
                    generate_create_schema_sql(schema), schema=None
                )
                logger.info("SchemaProvisioner: created schema %s", schema)
            # 元模型表始终确保 (IF NOT EXISTS 幂等)
            await self._client.execute(generate_meta_tables_sql(schema), schema=schema)
            logger.info("SchemaProvisioner: meta tables ensured for %s", schema)
        except ValueError:
            # schema 名校验失败, 不包装, 直接抛
            raise
        except Exception as e:
            raise ProvisionError(f"provision schema {schema} 失败: {e}") from e

    async def introspect(self, schema: str) -> dict:
        """读取元模型表, 返回领域结构概况。"""
        exists = await self._client.schema_exists(schema)
        if not exists:
            return {"schema": schema, "exists": False}

        entities = await self._client.fetchval(
            f'SELECT count(*) FROM "{schema}"._meta_entities', schema=schema
        )
        states = await self._client.fetchval(
            f'SELECT count(*) FROM "{schema}"._meta_states', schema=schema
        )
        transitions = await self._client.fetchval(
            f'SELECT count(*) FROM "{schema}"._meta_transitions', schema=schema
        )
        policies = await self._client.fetchval(
            f'SELECT count(*) FROM "{schema}"._meta_policies', schema=schema
        )
        return {
            "schema": schema,
            "exists": True,
            "entities_count": entities or 0,
            "states_count": states or 0,
            "transitions_count": transitions or 0,
            "policies_count": policies or 0,
        }
