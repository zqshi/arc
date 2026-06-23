"""Supabase PG 连接管理 (v5.6.0 T3)。

asyncpg 直连执行 raw DDL/DML (ORM 不适合 CREATE SCHEMA 等 DDL)。
schema 隔离: 每个 Arc Project 的表在 arc_{project_id} schema 下,
通过 SET search_path 隔离, 避免与 Arc 自身元数据表冲突。

DSN 解析:
- 显式 supabase_db_url → 生产指向真实 Supabase Postgres
- 留空 → 复用 Arc database_url (dev: 生成的应用 schema 与 Arc 元数据同库隔离)
"""
from __future__ import annotations

import logging
from typing import Any

import asyncpg

from arc.config import settings
from arc.domain.baas.value_objects import SCHEMA_NAME_PREFIX

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Supabase Postgres 连接管理器。

    生命周期由调用方 (BaasService) 管理, 提供 acquire() 上下文拿原生连接。
    单例缓存 pool, 进程级复用。
    """

    _pool: asyncpg.Pool | None = None

    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or self._resolve_dsn()

    # --- DSN 解析 ---

    @staticmethod
    def _resolve_dsn() -> str:
        if settings.supabase_db_url:
            return settings.supabase_db_url
        # dev fallback: 复用 Arc 的 database_url, 去掉 SQLAlchemy driver 后缀
        return SupabaseClient._normalize_dsn(settings.database_url)

    @staticmethod
    def _normalize_dsn(dsn: str) -> str:
        """去掉 SQLAlchemy +asyncpg driver 后缀, 转纯 asyncpg DSN。"""
        return dsn.replace("postgresql+asyncpg://", "postgresql://")

    # --- schema 名校验 (防 SQL 注入 + 约定一致) ---

    @staticmethod
    def _assert_valid_schema_name(schema: str) -> None:
        """schema 名必须有 arc_ 前缀且仅含安全字符 (字母数字下划线)。"""
        if not schema:
            raise ValueError("schema 名不能为空")
        if not schema.startswith(SCHEMA_NAME_PREFIX):
            raise ValueError(
                f"schema 名必须以 '{SCHEMA_NAME_PREFIX}' 前缀开头, 得到: {schema}"
            )
        # 仅允许 [a-zA-Z0-9_], 防 SET search_path 注入
        import re
        if not re.fullmatch(r"[a-zA-Z0-9_]+", schema):
            raise ValueError(f"schema 名含非法字符: {schema}")

    # --- 连接管理 ---

    async def get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
            logger.info("SupabaseClient pool created for %s", self._dsn_host_safe())
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def _dsn_host_safe(self) -> str:
        """日志用, 隐藏密码。"""
        # dsn 形如 postgresql://user:pw@host:5432/db
        try:
            rest = self._dsn.split("@", 1)[1] if "@" in self._dsn else self._dsn
            return rest
        except Exception:
            return "(unknown)"

    # --- 执行 ---

    async def execute(
        self,
        sql: str,
        *args: Any,
        schema: str | None = None,
        conn: asyncpg.Connection | None = None,
    ) -> str:
        """在指定 schema 的 search_path 下执行 SQL, 返回状态字符串。

        Args:
            schema: 目标 schema (arc_ 前缀), None 时用默认 search_path
            conn: 复用外部连接 (事务内多步操作), None 时从 pool 取
        """
        own_conn = conn is None
        if conn is None:
            pool = await self.get_pool()
            conn = await pool.acquire()

        try:
            if schema is not None:
                self._assert_valid_schema_name(schema)
                # 先 SET search_path 到目标 schema, 再执行业务 SQL
                await conn.execute(f'SET search_path TO "{schema}", public')
            result = await conn.execute(sql, *args)
            return result
        finally:
            if own_conn:
                await self._release(conn)

    async def _release(self, conn: asyncpg.Connection) -> None:
        if self._pool is not None:
            await self._pool.release(conn)

    async def schema_exists(self, schema: str, conn: asyncpg.Connection | None = None) -> bool:
        """检查 schema 是否已存在。"""
        self._assert_valid_schema_name(schema)
        own_conn = conn is None
        if conn is None:
            pool = await self.get_pool()
            conn = await pool.acquire()
        try:
            val = await conn.fetchval(
                "SELECT 1 FROM pg_namespace WHERE nspname = $1", schema
            )
            return val is not None
        finally:
            if own_conn:
                await self._release(conn)

    async def fetchval(
        self, sql: str, *args: Any, schema: str | None = None
    ) -> Any:
        """取单值 (供 provisioner/introspection 用)。"""
        own_conn = False
        conn: asyncpg.Connection | None = None
        if True:
            pool = await self.get_pool()
            conn = await pool.acquire()
            own_conn = True
        assert conn is not None
        try:
            if schema is not None:
                self._assert_valid_schema_name(schema)
                await conn.execute(f'SET search_path TO "{schema}", public')
            return await conn.fetchval(sql, *args)
        finally:
            if own_conn:
                await self._release(conn)
