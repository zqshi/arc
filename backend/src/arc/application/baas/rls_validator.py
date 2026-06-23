"""RLS 安全校验 (v5.6.0 T17)。

借鉴 XSpace _validate_user_owned_table_sql 的 5 项关键检查, 校验 Agent 生成的
BaasSchema 的 RLS 安全性。不阻断, 返回 warnings 列表供人工审批 gate。

检查项:
1. 表启用 RLS (has_rls)
2. user_id 列有 DEFAULT auth.uid() (防前端伪造 owner)
3. 有 user_id 的表存在 authenticated SELECT 策略
4. INSERT 策略有 WITH CHECK (防越权写入)
5. 无 anon using 'true' 全放行 (critical, 数据泄漏风险)
"""
from __future__ import annotations

from dataclasses import dataclass

from arc.domain.baas.value_objects import BaasSchema, ColumnDef, RlsPolicy, TableDef


@dataclass(frozen=True)
class RlsWarning:
    """RLS 校验警告 (不阻断)。"""

    table: str
    message: str
    severity: str = "warning"  # warning | critical


def validate_rls(schema: BaasSchema) -> list[RlsWarning]:
    """校验 schema 的 RLS 配置, 返回警告列表 (空 = 无问题)。"""
    warnings: list[RlsWarning] = []
    policies_by_table = _index_policies(schema.policies)

    for table in schema.tables:
        warnings.extend(_check_table(table, policies_by_table.get(table.name, [])))

    return warnings


def _index_policies(policies: list[RlsPolicy]) -> dict[str, list[RlsPolicy]]:
    index: dict[str, list[RlsPolicy]] = {}
    for p in policies:
        index.setdefault(p.table_name, []).append(p)
    return index


def _check_table(table: TableDef, policies: list[RlsPolicy]) -> list[RlsWarning]:
    warnings: list[RlsWarning] = []

    # 1. RLS 启用检查
    if not table.has_rls:
        warnings.append(RlsWarning(
            table=table.name,
            message=f"表 {table.name} 未启用 RLS, 数据无权限隔离",
            severity="critical",
        ))

    # 2. user_id DEFAULT 检查
    user_id_col = _find_user_id_column(table)
    if user_id_col is not None:
        if user_id_col.default != "auth.uid()":
            warnings.append(RlsWarning(
                table=table.name,
                message=(
                    f"user_id 列缺少 DEFAULT auth.uid(), 前端可伪造 owner "
                    f"(当前 default={user_id_col.default!r})"
                ),
            ))

    # 3. authenticated SELECT 策略 (仅 user_id 表强制, 字典表不强制)
    if user_id_col is not None:
        has_select = any(
            p.operation == "SELECT" and p.role == "authenticated" for p in policies
        )
        if not has_select:
            warnings.append(RlsWarning(
                table=table.name,
                message=f"表 {table.name} 有 user_id 但缺 authenticated SELECT 策略",
            ))

    # 4. INSERT 策略 WITH CHECK
    insert_policies = [p for p in policies if p.operation == "INSERT"]
    for p in insert_policies:
        if p.check_expr is None:
            warnings.append(RlsWarning(
                table=table.name,
                message=f"INSERT 策略 ({p.role}) 缺 WITH CHECK, 可越权写入任意 user_id",
            ))

    # 5. anon 全放行
    for p in policies:
        if (
            p.role == "anon"
            and p.using_expr is not None
            and p.using_expr.strip().lower() == "true"
        ):
            warnings.append(RlsWarning(
                table=table.name,
                message=(
                    f"anon {p.operation} 策略 using 'true' 全放行, 存在数据泄漏风险"
                ),
                severity="critical",
            ))

    return warnings


def _find_user_id_column(table: TableDef) -> ColumnDef | None:
    for col in table.columns:
        if col.name == "user_id":
            return col
    return None
