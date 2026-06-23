"""Tests for rls_generator (v5.6.0 T6).

RlsPolicy → CREATE POLICY SQL。纯函数, 验证生成的 SQL 结构和安全性。
"""
from __future__ import annotations

import pytest

from arc.domain.baas.value_objects import RlsPolicy
from arc.infrastructure.baas.rls_generator import generate_policy_sql


class TestGeneratePolicySql:
    def test_select_policy(self):
        policy = RlsPolicy(
            table_name="posts", operation="SELECT", role="authenticated",
            using_expr="auth.uid() = user_id",
        )
        sql = generate_policy_sql(policy, schema="arc_test123")
        assert "CREATE POLICY" in sql
        assert "FOR SELECT" in sql
        assert "TO authenticated" in sql
        assert "USING (auth.uid() = user_id)" in sql
        assert "arc_test123" in sql
        # SELECT 不应有 WITH CHECK
        assert "WITH CHECK" not in sql

    def test_insert_policy_requires_check(self):
        policy = RlsPolicy(
            table_name="posts", operation="INSERT", role="authenticated",
            check_expr="auth.uid() = user_id",
        )
        sql = generate_policy_sql(policy, schema="arc_test123")
        assert "FOR INSERT" in sql
        assert "WITH CHECK (auth.uid() = user_id)" in sql
        # INSERT 不应有 USING
        assert "USING" not in sql

    def test_update_policy_can_have_both(self):
        """UPDATE 可同时有 USING (限制可见行) 和 WITH CHECK (限制新值)。"""
        policy = RlsPolicy(
            table_name="posts", operation="UPDATE", role="authenticated",
            using_expr="auth.uid() = user_id",
            check_expr="auth.uid() = user_id",
        )
        sql = generate_policy_sql(policy, schema="arc_test123")
        assert "FOR UPDATE" in sql
        assert "USING" in sql
        assert "WITH CHECK" in sql

    def test_delete_policy(self):
        policy = RlsPolicy(
            table_name="posts", operation="DELETE", role="authenticated",
            using_expr="auth.uid() = user_id",
        )
        sql = generate_policy_sql(policy, schema="arc_test123")
        assert "FOR DELETE" in sql
        assert "USING" in sql
        assert "WITH CHECK" not in sql

    def test_anon_role(self):
        policy = RlsPolicy(
            table_name="posts", operation="SELECT", role="anon",
            using_expr="true",
        )
        sql = generate_policy_sql(policy, schema="arc_test123")
        assert "TO anon" in sql

    def test_invalid_operation_raises(self):
        policy = RlsPolicy(
            table_name="posts", operation="TRUNCATE", role="authenticated",
        )
        with pytest.raises(ValueError, match="不支持的 RLS 操作"):
            generate_policy_sql(policy, schema="arc_test123")

    def test_invalid_table_name_rejected(self):
        """表名含特殊字符防注入。"""
        policy = RlsPolicy(
            table_name="posts; DROP TABLE users; --", operation="SELECT", role="anon",
            using_expr="true",
        )
        with pytest.raises(ValueError, match="非法字符"):
            generate_policy_sql(policy, schema="arc_test123")

    def test_invalid_role_rejected(self):
        """role 名防注入 (仅允许 authenticated/anon/service_role)。"""
        policy = RlsPolicy(
            table_name="posts", operation="SELECT",
            role="authenticated; DROP POLICY x", using_expr="true",
        )
        with pytest.raises(ValueError, match="role"):
            generate_policy_sql(policy, schema="arc_test123")

    def test_policy_name_generated(self):
        """策略名应可读且唯一 (table_op_role)。"""
        policy = RlsPolicy(
            table_name="posts", operation="SELECT", role="authenticated",
            using_expr="true",
        )
        sql = generate_policy_sql(policy, schema="arc_test123")
        # 策略名含表名+操作+角色
        assert "posts_select_authenticated" in sql

    def test_idempotent(self):
        """CREATE POLICY 用 IF NOT EXISTS? 实际 PG 不支持, 需 DROP IF EXISTS + CREATE。
        验证生成的是 DROP + CREATE 序列 (幂等)。"""
        policy = RlsPolicy(
            table_name="posts", operation="SELECT", role="authenticated",
            using_expr="true",
        )
        sql = generate_policy_sql(policy, schema="arc_test123")
        assert "DROP POLICY IF EXISTS" in sql
        assert "CREATE POLICY" in sql
