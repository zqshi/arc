"""RlsPolicy → CREATE POLICY SQL 生成器 (v5.6.0 T6)。

纯函数: RlsPolicy 值对象 → 可执行 RLS 策略 SQL。

PostgreSQL RLS 语义:
- USING: 限制哪些行可见/可改 (SELECT/UPDATE/DELETE 的行过滤)
- WITH CHECK: 限制新写入的行 (INSERT/UPDATE 的新值校验)
- INSERT 只用 WITH CHECK; DELETE 只用 USING; UPDATE 可两者; SELECT 只用 USING

幂等: DROP POLICY IF EXISTS + CREATE POLICY (PG 的 CREATE POLICY 不支持 IF NOT EXISTS)。
"""
from __future__ import annotations

import re

from arc.domain.baas.value_objects import RlsPolicy
from arc.infrastructure.baas.sql_generator import _assert_ident
from arc.infrastructure.baas.supabase_client import SupabaseClient

# 合法操作 (大写)
_VALID_OPERATIONS = {"SELECT", "INSERT", "UPDATE", "DELETE"}

# 合法 role (防 SQL 注入; service_role 走内部信任, 通常不写 RLS)
_VALID_ROLES = {"authenticated", "anon", "service_role"}

# 各操作需要的表达式类型
_NEEDS_USING = {"SELECT", "UPDATE", "DELETE"}
_NEEDS_CHECK = {"INSERT", "UPDATE"}


def _policy_name(policy: RlsPolicy) -> str:
    """生成可读且唯一的策略名: table_operation_role。"""
    return f"{policy.table_name}_{policy.operation.lower()}_{policy.role}"


def generate_policy_sql(policy: RlsPolicy, schema: str) -> str:
    """生成 DROP + CREATE POLICY 语句 (幂等)。"""
    SupabaseClient._assert_valid_schema_name(schema)
    _assert_ident(policy.table_name, "表名")

    op = policy.operation.upper()
    if op not in _VALID_OPERATIONS:
        raise ValueError(
            f"不支持的 RLS 操作: {policy.operation!r} (仅 {sorted(_VALID_OPERATIONS)})"
        )

    if policy.role not in _VALID_ROLES:
        raise ValueError(
            f"非法 role: {policy.role!r} (仅 {sorted(_VALID_ROLES)})"
        )

    name = _policy_name(policy)
    _assert_ident(name, "策略名")

    parts = [
        f'DROP POLICY IF EXISTS "{name}" ON "{schema}"."{policy.table_name}";',
        f'CREATE POLICY "{name}" ON "{schema}"."{policy.table_name}"',
        f"    FOR {op} TO {policy.role}",
    ]

    if op in _NEEDS_USING:
        using = policy.using_expr or "false"
        parts.append(f"    USING ({using})")
    if op in _NEEDS_CHECK:
        check = policy.check_expr or "false"
        parts.append(f"    WITH CHECK ({check})")

    return "\n".join(parts) + ";"
