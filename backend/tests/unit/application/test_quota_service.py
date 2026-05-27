from __future__ import annotations

from arc.application.billing.quota_service import UsageSummary


class TestUsageSummary:
    def test_creation(self) -> None:
        s = UsageSummary(
            plan="free",
            projects_used=2,
            projects_limit=5,
            members_used=1,
            members_limit=3,
            ai_calls_today=10,
            ai_calls_limit=100,
        )
        assert s.plan == "free"
        assert s.projects_used == 2
        assert s.projects_limit == 5
        assert s.ai_calls_today == 10

    def test_over_limit_scenario(self) -> None:
        s = UsageSummary(
            plan="pro",
            projects_used=10,
            projects_limit=10,
            members_used=5,
            members_limit=5,
            ai_calls_today=500,
            ai_calls_limit=500,
        )
        assert s.projects_used == s.projects_limit
        assert s.ai_calls_today == s.ai_calls_limit
