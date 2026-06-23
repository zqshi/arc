"""BaaS 值对象 (v5.6.0 T1)。

定义 Supabase schema 的领域模型：表/列/RLS 策略/状态机/Action。
这些值对象是 DomainModelSnapshot → SQL 的中间表示，也是 Agent 生成的产物。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from arc.domain.baas.errors import SchemaApplyError

# Supabase schema 隔离约定前缀 — 每个 Arc Project 对应一个独立 schema
SCHEMA_NAME_PREFIX = "arc_"


class BaasStatus(StrEnum):
    """BaasInstance 生命周期状态。"""

    PROVISIONING = "provisioning"  # 正在创建 schema + 元模型
    ACTIVE = "active"  # schema 就绪，可应用 DomainModel
    SUSPENDED = "suspended"  # 暂停 (资源/计费)
    DELETED = "deleted"  # 软删除


# 状态转换合法性表
VALID_BAAS_TRANSITIONS: dict[BaasStatus, set[BaasStatus]] = {
    BaasStatus.PROVISIONING: {BaasStatus.ACTIVE},
    BaasStatus.ACTIVE: {BaasStatus.SUSPENDED, BaasStatus.DELETED},
    BaasStatus.SUSPENDED: {BaasStatus.ACTIVE, BaasStatus.DELETED},
    BaasStatus.DELETED: set(),  # 终态
}


@dataclass(frozen=True)
class ColumnDef:
    """列定义 — 映射到 SQL DDL 的单列。

    type 用 PostgreSQL 类型名 (uuid/text/int/timestamptz/boolean/jsonb)，
    default 存 SQL 表达式 (如 "auth.uid()", "now()")。
    """

    name: str
    type: str
    nullable: bool = True
    default: str | None = None
    is_primary: bool = False
    references: str | None = None  # "other_table(id)" 外键引用


@dataclass(frozen=True)
class TableDef:
    """表定义 — 含列、RLS 开关、状态机元信息。"""

    name: str
    columns: list[ColumnDef]
    has_rls: bool = True
    has_state_machine: bool = False
    state_field: str | None = None


@dataclass(frozen=True)
class RlsPolicy:
    """RLS 策略 — 映射到 CREATE POLICY。

    operation: SELECT/INSERT/UPDATE/DELETE
    using_expr: SELECT/UPDATE/DELETE 的 WHERE 条件
    check_expr: INSERT/UPDATE 的 WITH CHECK 表达式
    """

    table_name: str
    operation: str
    role: str  # authenticated/anon/service_role
    using_expr: str | None = None
    check_expr: str | None = None


@dataclass(frozen=True)
class StateTransition:
    """状态跃迁定义 — 描述业务合法转换。

    guard 是 SQL-like 前置条件描述 (如 "amount > 0")，
    由 rls_validator 检查，Action 执行时校验。
    """

    entity: str
    from_state: str
    to_state: str
    action_name: str
    guard: str


@dataclass(frozen=True)
class ActionDef:
    """业务动作定义 → 生成 Supabase Edge Function。

    RLS 管"谁能访问"，Action 管"这次操作是否合法"。
    transition 为 None 表示非状态变更动作 (如通知/查询)。
    """

    name: str
    entity: str
    transition: StateTransition | None
    preconditions: list[str] = field(default_factory=list)  # 自然语言前置条件
    effects: list[str] = field(default_factory=list)  # 写入副作用
    is_idempotent: bool = False


@dataclass(frozen=True)
class BaasSchema:
    """一个项目的完整 BaaS Schema 定义。

    schema_name 必须有 arc_ 前缀 (Supabase schema 隔离约定，见 SCHEMA_NAME_PREFIX)。
    """

    schema_name: str
    tables: list[TableDef] = field(default_factory=list)
    policies: list[RlsPolicy] = field(default_factory=list)
    transitions: list[StateTransition] = field(default_factory=list)
    actions: list[ActionDef] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.schema_name.startswith(SCHEMA_NAME_PREFIX):
            raise SchemaApplyError(
                f"schema_name 必须以 '{SCHEMA_NAME_PREFIX}' 前缀开头，"
                f"得到: {self.schema_name}"
            )
