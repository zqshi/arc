"""Tests for RLS validator (v5.6.0 T17).

校验 Agent 生成的 BaasSchema 的 RLS 安全性, 借鉴 XSpace 5 项检查。
不阻断, 返回 warnings 列表 (人工审批 gate)。
"""
from __future__ import annotations

from arc.application.baas.rls_validator import validate_rls
from arc.domain.baas.value_objects import (
    BaasSchema,
    ColumnDef,
    RlsPolicy,
    TableDef,
)


def _make_schema(
    *, tables: list[TableDef], policies: list[RlsPolicy]
) -> BaasSchema:
    return BaasSchema(
        schema_name="arc_test",
        tables=tables,
        policies=policies,
    )


class TestValidateRls:
    def test_clean_schema_no_warnings(self):
        """规范 schema: RLS 启用 + user_id DEFAULT + authenticated SELECT/INSERT。"""
        schema = _make_schema(
            tables=[
                TableDef(
                    name="posts",
                    columns=[
                        ColumnDef(name="id", type="uuid", is_primary=True, nullable=False),
                        ColumnDef(
                            name="user_id", type="uuid", nullable=False,
                            default="auth.uid()",
                        ),
                    ],
                    has_rls=True,
                ),
            ],
            policies=[
                RlsPolicy(table_name="posts", operation="SELECT", role="authenticated",
                          using_expr="auth.uid() = user_id"),
                RlsPolicy(table_name="posts", operation="INSERT", role="authenticated",
                          check_expr="auth.uid() = user_id"),
            ],
        )
        warnings = validate_rls(schema)
        assert warnings == []

    def test_rls_disabled_warning(self):
        """表未启用 RLS → 警告。"""
        schema = _make_schema(
            tables=[
                TableDef(
                    name="posts",
                    columns=[ColumnDef(name="id", type="uuid", is_primary=True)],
                    has_rls=False,
                ),
            ],
            policies=[],
        )
        warnings = validate_rls(schema)
        assert any("posts" in w.table for w in warnings)
        assert any("未启用 RLS" in w.message for w in warnings)

    def test_user_id_missing_default_warning(self):
        """有 user_id 列但无 DEFAULT auth.uid() → 警告 (XSpace 关键检查)。"""
        schema = _make_schema(
            tables=[
                TableDef(
                    name="posts",
                    columns=[
                        ColumnDef(name="id", type="uuid", is_primary=True),
                        ColumnDef(name="user_id", type="uuid"),  # 无 default
                    ],
                    has_rls=True,
                ),
            ],
            policies=[],
        )
        warnings = validate_rls(schema)
        assert any("user_id" in w.message and "DEFAULT" in w.message for w in warnings)

    def test_select_policy_missing_warning(self):
        """有 user_id 的表缺 authenticated SELECT 策略 → 警告。"""
        schema = _make_schema(
            tables=[
                TableDef(
                    name="posts",
                    columns=[
                        ColumnDef(name="id", type="uuid", is_primary=True),
                        ColumnDef(name="user_id", type="uuid", default="auth.uid()"),
                    ],
                    has_rls=True,
                ),
            ],
            policies=[],  # 无 SELECT 策略
        )
        warnings = validate_rls(schema)
        assert any("SELECT" in w.message for w in warnings)

    def test_insert_policy_missing_check_warning(self):
        """INSERT 策略缺 WITH CHECK → 警告 (XSpace: 防越权写入)。"""
        schema = _make_schema(
            tables=[
                TableDef(
                    name="posts",
                    columns=[
                        ColumnDef(name="id", type="uuid", is_primary=True),
                        ColumnDef(name="user_id", type="uuid", default="auth.uid()"),
                    ],
                    has_rls=True,
                ),
            ],
            policies=[
                RlsPolicy(table_name="posts", operation="INSERT", role="authenticated",
                          check_expr=None),  # 缺 check
            ],
        )
        warnings = validate_rls(schema)
        assert any("WITH CHECK" in w.message for w in warnings)

    def test_anon_full_disclosure_warning(self):
        """anon SELECT using 'true' → 高危警告 (全放行)。"""
        schema = _make_schema(
            tables=[
                TableDef(
                    name="posts",
                    columns=[ColumnDef(name="id", type="uuid", is_primary=True)],
                    has_rls=True,
                ),
            ],
            policies=[
                RlsPolicy(table_name="posts", operation="SELECT", role="anon",
                          using_expr="true"),
            ],
        )
        warnings = validate_rls(schema)
        assert any("anon" in w.message and "true" in w.message for w in warnings)

    def test_table_without_user_id_no_select_warning(self):
        """无 user_id 的表 (如字典表) 不强制要求 SELECT 策略。"""
        schema = _make_schema(
            tables=[
                TableDef(
                    name="categories",
                    columns=[ColumnDef(name="id", type="uuid", is_primary=True)],
                    has_rls=True,
                ),
            ],
            policies=[],
        )
        warnings = validate_rls(schema)
        # 无 user_id 表不要求 SELECT 策略, 但 RLS 已启用, 应无警告
        assert warnings == []

    def test_warning_severity(self):
        """anon 全放行是 critical, 其他是 warning。"""
        schema = _make_schema(
            tables=[
                TableDef(
                    name="posts",
                    columns=[ColumnDef(name="id", type="uuid", is_primary=True)],
                    has_rls=True,
                ),
            ],
            policies=[
                RlsPolicy(table_name="posts", operation="SELECT", role="anon",
                          using_expr="true"),
            ],
        )
        warnings = validate_rls(schema)
        critical = [w for w in warnings if w.severity == "critical"]
        assert len(critical) >= 1
