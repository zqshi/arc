"""Tests for domain/baas value objects (v5.6.0 T1)."""

from arc.domain.baas.errors import ProvisionError, SchemaApplyError
from arc.domain.baas.value_objects import (
    ActionDef,
    BaasSchema,
    BaasStatus,
    ColumnDef,
    RlsPolicy,
    StateTransition,
    TableDef,
)


class TestColumnDef:
    def test_minimal_creation(self):
        col = ColumnDef(name="id", type="uuid")
        assert col.name == "id"
        assert col.type == "uuid"
        assert col.nullable is True  # 默认可空
        assert col.default is None
        assert col.is_primary is False
        assert col.references is None

    def test_primary_key_column(self):
        col = ColumnDef(
            name="id", type="uuid", nullable=False, default="gen_random_uuid()", is_primary=True
        )
        assert col.is_primary is True
        assert col.nullable is False

    def test_foreign_key_column(self):
        col = ColumnDef(name="user_id", type="uuid", references="users(id)", nullable=False)
        assert col.references == "users(id)"

    def test_immutable(self):
        col = ColumnDef(name="id", type="uuid")
        try:
            col.name = "changed"
            assert False, "frozen dataclass should be immutable"
        except AttributeError:
            pass


class TestTableDef:
    def test_minimal_creation(self):
        table = TableDef(name="posts", columns=[ColumnDef(name="id", type="uuid")])
        assert table.name == "posts"
        assert table.has_rls is True  # 默认启用 RLS
        assert table.has_state_machine is False
        assert table.state_field is None

    def test_state_machine_table(self):
        table = TableDef(
            name="orders",
            columns=[ColumnDef(name="id", type="uuid"), ColumnDef(name="status", type="text")],
            has_state_machine=True,
            state_field="status",
        )
        assert table.has_state_machine is True
        assert table.state_field == "status"

    def test_primary_key_detection(self):
        """无显式主键时表仍有效，但 SQL 生成器应能识别。"""
        table = TableDef(
            name="t",
            columns=[
                ColumnDef(name="id", type="uuid", is_primary=True),
                ColumnDef(name="name", type="text"),
            ],
        )
        pks = [c for c in table.columns if c.is_primary]
        assert len(pks) == 1
        assert pks[0].name == "id"


class TestRlsPolicy:
    def test_select_policy(self):
        policy = RlsPolicy(
            table_name="posts", operation="SELECT", role="authenticated",
            using_expr="auth.uid() = user_id",
        )
        assert policy.operation == "SELECT"
        assert policy.check_expr is None  # SELECT 不需要 WITH CHECK

    def test_insert_policy_requires_check(self):
        policy = RlsPolicy(
            table_name="posts", operation="INSERT", role="authenticated",
            check_expr="auth.uid() = user_id",
        )
        assert policy.check_expr is not None
        assert policy.using_expr is None


class TestStateTransition:
    def test_creation(self):
        t = StateTransition(
            entity="order", from_state="pending", to_state="paid",
            action_name="pay", guard="amount > 0",
        )
        assert t.entity == "order"
        assert t.from_state == "pending"
        assert t.to_state == "paid"

    def test_immutable(self):
        t = StateTransition(
            entity="o", from_state="a", to_state="b", action_name="x", guard="true"
        )
        try:
            t.to_state = "c"
            assert False
        except AttributeError:
            pass


class TestActionDef:
    def test_action_with_transition(self):
        action = ActionDef(
            name="pay_order", entity="order",
            transition=StateTransition(
                entity="order", from_state="pending", to_state="paid",
                action_name="pay", guard="amount > 0",
            ),
            preconditions=["订单存在", "用户已认证"],
            effects=["扣减库存", "记录支付流水"],
        )
        assert action.transition is not None
        assert action.transition.to_state == "paid"
        assert action.is_idempotent is False

    def test_action_without_transition(self):
        """非状态变更动作 (如纯查询/通知) 无 transition。"""
        action = ActionDef(
            name="notify_user", entity="user", transition=None,
            preconditions=[], effects=["发送通知"],
        )
        assert action.transition is None


class TestBaasSchema:
    def test_minimal_schema(self):
        schema = BaasSchema(
            schema_name="arc_proj123",
            tables=[TableDef(name="users", columns=[ColumnDef(name="id", type="uuid", is_primary=True)])],
            policies=[],
            transitions=[],
            actions=[],
        )
        assert schema.schema_name == "arc_proj123"
        assert len(schema.tables) == 1

    def test_schema_name_prefix_validation(self):
        """schema_name 必须有 arc_ 前缀 (Supabase schema 隔离约定)。"""
        try:
            BaasSchema(
                schema_name="proj123",  # 缺前缀
                tables=[], policies=[], transitions=[], actions=[],
            )
            assert False, "应抛 SchemaApplyError"
        except SchemaApplyError:
            pass

    def test_full_schema(self):
        schema = BaasSchema(
            schema_name="arc_shop",
            tables=[
                TableDef(name="orders", columns=[
                    ColumnDef(name="id", type="uuid", is_primary=True, nullable=False),
                    ColumnDef(name="status", type="text", nullable=False),
                ], has_state_machine=True, state_field="status"),
            ],
            policies=[
                RlsPolicy(table_name="orders", operation="SELECT", role="authenticated",
                          using_expr="auth.uid() = user_id"),
            ],
            transitions=[
                StateTransition(entity="orders", from_state="pending", to_state="paid",
                                action_name="pay", guard="amount > 0"),
            ],
            actions=[
                ActionDef(name="pay_order", entity="orders",
                          transition=None, preconditions=[], effects=[]),
            ],
        )
        assert len(schema.policies) == 1
        assert len(schema.transitions) == 1


class TestBaasStatus:
    def test_values(self):
        assert BaasStatus.PROVISIONING == "provisioning"
        assert BaasStatus.ACTIVE == "active"
        assert BaasStatus.SUSPENDED == "suspended"
        assert BaasStatus.DELETED == "deleted"

    def test_completeness(self):
        expected = {"provisioning", "active", "suspended", "deleted"}
        assert {s.value for s in BaasStatus} == expected


class TestErrors:
    def test_provision_error_is_domain_error(self):
        from arc.domain.errors import DomainError

        err = ProvisionError("连接失败")
        assert isinstance(err, DomainError)
        assert err.detail == "连接失败"

    def test_schema_apply_error(self):
        from arc.domain.errors import DomainError

        err = SchemaApplyError("字段冲突")
        assert isinstance(err, DomainError)
        assert err.detail == "字段冲突"
