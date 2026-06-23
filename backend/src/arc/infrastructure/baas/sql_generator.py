"""BaasSchema → DDL SQL 生成器 (v5.6.0 T5)。

纯函数: BaasSchema 值对象 → 可执行 SQL 字符串。
安全: 表名/列名/schema 名白名单校验, 防 SQL 注入。
增量 DDL 约定: 全部 IF NOT EXISTS, 不允许 DROP (防数据丢失, 见 plan 约束)。
"""
from __future__ import annotations

import re

from arc.domain.baas.value_objects import ColumnDef, TableDef
from arc.infrastructure.baas.supabase_client import SupabaseClient

# 标识符白名单: 字母数字下划线 (防 SQL 注入)
_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Python 类型 → PostgreSQL 类型映射 (Agent 可用简写, 这里规范化)
_TYPE_MAP: dict[str, str] = {
    "uuid": "UUID",
    "text": "TEXT",
    "int": "INTEGER",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "timestamptz": "TIMESTAMPTZ",
    "timestamp": "TIMESTAMP",
    "jsonb": "JSONB",
    "json": "JSON",
    "numeric": "NUMERIC",
    "real": "REAL",
    "date": "DATE",
}


def to_sql_type(py_type: str) -> str:
    """Python 类型简写 → PostgreSQL 类型。未知类型原样透传 (信任 Agent)。"""
    # 保留带参数的类型如 numeric(10,2)
    base = py_type.split("(", 1)[0].strip().lower()
    mapped = _TYPE_MAP.get(base)
    if mapped and "(" in py_type:
        return f"{mapped}{py_type[py_type.index('('):]}"
    return mapped or py_type


def _assert_ident(name: str, kind: str = "标识符") -> None:
    if not _IDENT_RE.fullmatch(name):
        raise ValueError(f"{kind}含非法字符: {name!r}")


def generate_create_schema_sql(schema: str) -> str:
    """生成 CREATE SCHEMA IF NOT EXISTS 语句。"""
    SupabaseClient._assert_valid_schema_name(schema)
    return f'CREATE SCHEMA IF NOT EXISTS "{schema}";'


def generate_meta_tables_sql(schema: str) -> str:
    """生成元模型表 (借鉴 XSpace _meta_*)。

    Agent 通过 get_domain_model tool 读取这些表, 了解当前应用领域结构后做增量变更。
    """
    SupabaseClient._assert_valid_schema_name(schema)
    return f"""-- 元模型表: 实体/状态/跃迁/权限声明
CREATE TABLE IF NOT EXISTS "{schema}"._meta_entities (
    name TEXT PRIMARY KEY,
    description TEXT,
    has_state_machine BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "{schema}"._meta_states (
    entity_name TEXT REFERENCES "{schema}"._meta_entities(name),
    state TEXT,
    description TEXT,
    is_initial BOOLEAN DEFAULT false,
    is_terminal BOOLEAN DEFAULT false,
    PRIMARY KEY (entity_name, state)
);

CREATE TABLE IF NOT EXISTS "{schema}"._meta_transitions (
    entity_name TEXT,
    from_state TEXT,
    to_state TEXT,
    action_name TEXT NOT NULL,
    guard_description TEXT,
    PRIMARY KEY (entity_name, from_state, to_state)
);

CREATE TABLE IF NOT EXISTS "{schema}"._meta_policies (
    table_name TEXT,
    operation TEXT,
    role TEXT,
    condition TEXT,
    PRIMARY KEY (table_name, operation, role)
);
"""


def _column_sql(col: ColumnDef, schema: str) -> str:
    """单列 DDL 片段。"""
    _assert_ident(col.name, "列名")
    parts = [col.name, to_sql_type(col.type)]
    if col.is_primary and not col.nullable:
        pass  # PRIMARY KEY 在表级处理
    else:
        if not col.nullable:
            parts.append("NOT NULL")
    if col.default is not None:
        parts.append(f"DEFAULT {col.default}")
    if col.references is not None:
        parts.append(f"REFERENCES {col.references}")
    return " ".join(parts)


def generate_table_sql(table: TableDef, schema: str) -> str:
    """生成 CREATE TABLE + (可选) RLS 开关语句。"""
    SupabaseClient._assert_valid_schema_name(schema)
    _assert_ident(table.name, "表名")
    for col in table.columns:
        _assert_ident(col.name, "列名")

    cols_ddl = ",\n    ".join(_column_sql(c, schema) for c in table.columns)

    # 主键 (单列或复合)
    pk_cols = [c.name for c in table.columns if c.is_primary]
    pk_clause = f",\n    PRIMARY KEY ({', '.join(pk_cols)})" if pk_cols else ""

    sql = (
        f'CREATE TABLE IF NOT EXISTS "{schema}"."{table.name}" (\n'
        f"    {cols_ddl}{pk_clause}\n"
        f");"
    )

    if table.has_rls:
        sql += (
            f'\nALTER TABLE "{schema}"."{table.name}" ENABLE ROW LEVEL SECURITY;'
            f'\nALTER TABLE "{schema}"."{table.name}" FORCE ROW LEVEL SECURITY;'
        )
    return sql
