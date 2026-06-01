"""Tests for domain/organization value objects."""

from arc.domain.organization.value_objects import (
    PLAN_LIMITS,
    OrgPlan,
    OrgRole,
)


class TestOrgRole:
    def test_enum_values(self):
        assert OrgRole.OWNER == "owner"
        assert OrgRole.ADMIN == "admin"
        assert OrgRole.MEMBER == "member"

    def test_enum_completeness(self):
        expected = {"owner", "admin", "member"}
        assert {r.value for r in OrgRole} == expected

    def test_equality_same_value(self):
        assert OrgRole.OWNER == OrgRole("owner")

    def test_equality_string_coercion(self):
        assert OrgRole.MEMBER == "member"

    def test_invalid_value_raises(self):
        try:
            OrgRole("superadmin")
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestOrgPlan:
    def test_enum_values(self):
        assert OrgPlan.FREE == "free"
        assert OrgPlan.PRO == "pro"
        assert OrgPlan.TEAM == "team"

    def test_enum_completeness(self):
        expected = {"free", "pro", "team"}
        assert {p.value for p in OrgPlan} == expected

    def test_equality_same_value(self):
        assert OrgPlan.PRO == OrgPlan("pro")

    def test_equality_string_coercion(self):
        assert OrgPlan.TEAM == "team"

    def test_invalid_value_raises(self):
        try:
            OrgPlan("enterprise")
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestPlanLimits:
    def test_all_plans_have_limits(self):
        for plan in OrgPlan:
            assert plan in PLAN_LIMITS
            assert isinstance(PLAN_LIMITS[plan], dict)

    def test_required_limit_keys(self):
        required_keys = {
            "max_projects",
            "max_members",
            "max_todos_per_project",
            "max_ai_calls_per_day",
        }
        for plan in OrgPlan:
            assert set(PLAN_LIMITS[plan].keys()) == required_keys

    def test_all_limits_are_positive_integers(self):
        for plan in OrgPlan:
            for key, value in PLAN_LIMITS[plan].items():
                assert isinstance(value, int), f"{plan}.{key} should be int"
                assert value > 0, f"{plan}.{key} should be positive"

    def test_free_plan_limits(self):
        free = PLAN_LIMITS[OrgPlan.FREE]
        assert free["max_projects"] == 3
        assert free["max_members"] == 1
        assert free["max_todos_per_project"] == 20
        assert free["max_ai_calls_per_day"] == 50

    def test_pro_plan_limits(self):
        pro = PLAN_LIMITS[OrgPlan.PRO]
        assert pro["max_projects"] == 20
        assert pro["max_members"] == 1
        assert pro["max_todos_per_project"] == 200
        assert pro["max_ai_calls_per_day"] == 500

    def test_team_plan_limits(self):
        team = PLAN_LIMITS[OrgPlan.TEAM]
        assert team["max_projects"] == 100
        assert team["max_members"] == 50
        assert team["max_todos_per_project"] == 1000
        assert team["max_ai_calls_per_day"] == 5000

    def test_higher_plan_has_higher_or_equal_limits(self):
        """Plans should monotonically increase in all limits."""
        plans_ordered = [OrgPlan.FREE, OrgPlan.PRO, OrgPlan.TEAM]
        for i in range(len(plans_ordered) - 1):
            lower = PLAN_LIMITS[plans_ordered[i]]
            higher = PLAN_LIMITS[plans_ordered[i + 1]]
            for key in lower:
                assert higher[key] >= lower[key], (
                    f"{plans_ordered[i+1]}.{key} should >= {plans_ordered[i]}.{key}"
                )
