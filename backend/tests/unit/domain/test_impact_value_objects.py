"""ImpactReport 等值对象单元测试 (Phase 2 扩展)。"""

import uuid

from arc.domain.review.value_objects import (
    ImpactItem,
    ImpactReport,
    ModelChangeScope,
    RiskLevel,
)


class TestRiskLevel:
    def test_ordering(self):
        assert RiskLevel.NONE < RiskLevel.LOW < RiskLevel.MEDIUM < RiskLevel.HIGH < RiskLevel.CRITICAL

    def test_int_values(self):
        assert int(RiskLevel.NONE) == 0
        assert int(RiskLevel.CRITICAL) == 4


class TestImpactItem:
    def test_frozen(self):
        item = ImpactItem(
            todo_id=uuid.uuid4(),
            todo_title="需求A",
            current_phase="development",
            affected_aggregates=("Order", "Payment"),
            risk=RiskLevel.HIGH,
            recommendation="暂停",
        )
        assert item.risk == RiskLevel.HIGH
        try:
            item.risk = RiskLevel.LOW  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass

    def test_equality(self):
        tid = uuid.uuid4()
        args = dict(
            todo_id=tid,
            todo_title="t",
            current_phase="development",
            affected_aggregates=("Order",),
            risk=RiskLevel.MEDIUM,
            recommendation="check",
        )
        assert ImpactItem(**args) == ImpactItem(**args)


class TestImpactReport:
    def test_empty_report(self):
        r = ImpactReport(
            project_id=uuid.uuid4(),
            affected_aggregates=("Order",),
            change_scope=ModelChangeScope.ADDITIVE,
        )
        assert r.max_risk == RiskLevel.NONE
        assert r.has_critical is False
        assert r.blocked_count == 0

    def test_max_risk(self):
        items = (
            ImpactItem(uuid.uuid4(), "a", "dev", ("O",), RiskLevel.LOW, ""),
            ImpactItem(uuid.uuid4(), "b", "dev", ("O",), RiskLevel.HIGH, ""),
            ImpactItem(uuid.uuid4(), "c", "dev", ("O",), RiskLevel.MEDIUM, ""),
        )
        r = ImpactReport(
            project_id=uuid.uuid4(),
            affected_aggregates=("O",),
            change_scope=ModelChangeScope.STRUCTURAL,
            items=items,
        )
        assert r.max_risk == RiskLevel.HIGH

    def test_has_critical(self):
        items = (
            ImpactItem(uuid.uuid4(), "a", "dev", ("O",), RiskLevel.CRITICAL, ""),
        )
        r = ImpactReport(
            project_id=uuid.uuid4(),
            affected_aggregates=("O",),
            change_scope=ModelChangeScope.BREAKING,
            items=items,
        )
        assert r.has_critical is True

    def test_blocked_count(self):
        items = (
            ImpactItem(uuid.uuid4(), "a", "dev", ("O",), RiskLevel.LOW, ""),
            ImpactItem(uuid.uuid4(), "b", "dev", ("O",), RiskLevel.HIGH, ""),
            ImpactItem(uuid.uuid4(), "c", "dev", ("O",), RiskLevel.CRITICAL, ""),
        )
        r = ImpactReport(
            project_id=uuid.uuid4(),
            affected_aggregates=("O",),
            change_scope=ModelChangeScope.BREAKING,
            items=items,
        )
        assert r.blocked_count == 2
