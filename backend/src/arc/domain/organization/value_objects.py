from __future__ import annotations

from enum import StrEnum


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class OrgPlan(StrEnum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


PLAN_LIMITS: dict[OrgPlan, dict[str, int]] = {
    OrgPlan.FREE: {
        "max_projects": 3,
        "max_members": 1,
        "max_todos_per_project": 20,
        "max_ai_calls_per_day": 50,
    },
    OrgPlan.PRO: {
        "max_projects": 20,
        "max_members": 1,
        "max_todos_per_project": 200,
        "max_ai_calls_per_day": 500,
    },
    OrgPlan.TEAM: {
        "max_projects": 100,
        "max_members": 50,
        "max_todos_per_project": 1000,
        "max_ai_calls_per_day": 5000,
    },
}
