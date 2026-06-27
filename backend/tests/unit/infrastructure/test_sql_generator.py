"""Tests for sql_generator (v5.6.0 T5).

BaasSchema → DDL SQL 生成。纯函数无 IO, 测试验证生成 SQL 的结构和安全性。
"""
from __future__ import annotations

import pytest

from arc.domain.baas.value_objects import (
    ColumnDef,
    TableDef,
)
from arc.infrastructure.baas.sql_generator import (
    generate_create_schema_sql,
    generate_meta_tables_sql,
    generate_table_sql,
    to_sql_type,
)


class TestToSqlType:
    def test_known_types(self):
        assert to_sql_type("uuid") == "UUID"
        assert to_sql_type("text") == "TEXT"
        assert to_sql_type("int") == "INTEGER"
        assert to_sql_type("boolean") == "BOOLEAN"
        assert to_sql_type("timestamptz") == "TIMESTAMPTZ"
        assert to_sql_type("jsonb") == "JSONB"

    def test_unknown_type_passed_through(self):
        """未知类型原样透传 (信任 Agent, 不阻断; validator 后置校验)。"""
        assert to_sql_type("citext") == "citext"
        # 带参数的已知类型保留参数
        assert to_sql_type("numeric(10,2)").startswith("NUMERIC")


class TestGenerateCreateSchema:
    def test_basic(self):
        sql = generate_create_schema_sql("arc_test123")
        assert "CREATE SCHEMA IF NOT EXISTS" in sql
        assert "arc_test123" in sql

    def test_invalid_prefix_raises(self):
        with pytest.raises(ValueError, match="前缀"):
            generate_create_schema_sql("bad_schema")


class TestGenerateTableSql:
    def test_simple_table(self):
        table = TableDef(
            name="posts",
            columns=[
                ColumnDef(name="id", type="uuid", is_primary=True, nullable=False,
                          default="gen_random_uuid()"),
                ColumnDef(name="title", type="text", nullable=False),
                ColumnDef(name="created_at", type="timestamptz", default="now()"),
            ],
        )
        sql = generate_table_sql(table, schema="arc_test123")

        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert '"arc_test123"."posts"' in sql
        assert "id UUID" in sql
        assert "PRIMARY KEY" in sql
        assert "title TEXT NOT NULL" in sql
        assert "DEFAULT gen_random_uuid()" in sql
        assert "DEFAULT now()" in sql

    def test_rls_enabled_adds_alter(self):
        table = TableDef(
            name="posts",
            columns=[ColumnDef(name="id", type="uuid", is_primary=True, nullable=False)],
            has_rls=True,
        )
        sql = generate_table_sql(table, schema="arc_test123")
        assert "ENABLE ROW LEVEL SECURITY" in sql
        assert "FORCE ROW LEVEL SECURITY" in sql

    def test_rls_disabled_skips_alter(self):
        table = TableDef(
            name="posts",
            columns=[ColumnDef(name="id", type="uuid", is_primary=True, nullable=False)],
            has_rls=False,
        )
        sql = generate_table_sql(table, schema="arc_test123")
        assert "ROW LEVEL SECURITY" not in sql

    def test_foreign_key_reference(self):
        table = TableDef(
            name="comments",
            columns=[
                ColumnDef(name="id", type="uuid", is_primary=True, nullable=False),
                ColumnDef(name="post_id", type="uuid", references="posts(id)", nullable=False),
            ],
        )
        sql = generate_table_sql(table, schema="arc_test123")
        assert "REFERENCES posts(id)" in sql

    def test_composite_primary_key(self):
        table = TableDef(
            name="post_tags",
            columns=[
                ColumnDef(name="post_id", type="uuid", is_primary=True, nullable=False),
                ColumnDef(name="tag_id", type="uuid", is_primary=True, nullable=False),
            ],
        )
        sql = generate_table_sql(table, schema="arc_test123")
        assert "PRIMARY KEY (post_id, tag_id)" in sql

    def test_invalid_table_name_rejected(self):
        """表名含特殊字符应拒绝 (防 SQL 注入)。"""
        table = TableDef(
            name="posts; DROP TABLE users; --",
            columns=[ColumnDef(name="id", type="uuid", is_primary=True, nullable=False)],
        )
        with pytest.raises(ValueError, match="非法字符"):
            generate_table_sql(table, schema="arc_test123")


class TestGenerateMetaTables:
    def test_creates_all_meta_tables(self):
        sql = generate_meta_tables_sql(schema="arc_test123")
        # XSpace _meta_* 借鉴: entities/states/transitions/policies
        assert "_meta_entities" in sql
        assert "_meta_states" in sql
        assert "_meta_transitions" in sql
        assert "_meta_policies" in sql
        assert "arc_test123" in sql

    def test_meta_tables_idempotent(self):
        """元模型表用 IF NOT EXISTS, 可重复执行。"""
        sql = generate_meta_tables_sql(schema="arc_test123")
        assert "IF NOT EXISTS" in sql
