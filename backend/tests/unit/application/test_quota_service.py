"""QuotaService 单元测试。

QuotaService 强依赖 SQLAlchemy 查询，使用 mock 模拟数据库行为，
主要验证配额检查逻辑是否正确触发 ForbiddenError。
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.application.billing.quota_service import UsageSummary
from arc.domain.errors import ForbiddenError
from arc.domain.organization.value_objects import OrgPlan


def _make_service():
    """构造 QuotaService，mock db session。"""
    from arc.application.billing.quota_service import QuotaService

    db = MagicMock()
    svc = QuotaService(db)
    return svc, db


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


class TestGetOrgPlan:
    async def test_returns_plan_from_db(self) -> None:
        svc, db = _make_service()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = "pro"
        db.execute = AsyncMock(return_value=mock_result)

        plan = await svc.get_org_plan(uuid.uuid4())
        assert plan == OrgPlan.PRO

    async def test_returns_free_when_not_found(self) -> None:
        svc, db = _make_service()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        plan = await svc.get_org_plan(uuid.uuid4())
        assert plan == OrgPlan.FREE


class TestCheckProjectLimit:
    @patch("arc.application.billing.quota_service.settings")
    async def test_skips_in_debug_mode(self, mock_settings) -> None:
        mock_settings.debug = True
        svc, db = _make_service()

        await svc.check_project_limit(uuid.uuid4())
        db.execute.assert_not_called()

    @patch("arc.application.billing.quota_service.settings")
    async def test_passes_when_under_limit(self, mock_settings) -> None:
        mock_settings.debug = False
        svc, db = _make_service()

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = "free"
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1

        db.execute = AsyncMock(side_effect=[plan_result, count_result])

        await svc.check_project_limit(uuid.uuid4())

    @patch("arc.application.billing.quota_service.settings")
    async def test_raises_when_at_limit(self, mock_settings) -> None:
        mock_settings.debug = False
        svc, db = _make_service()

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = "free"
        count_result = MagicMock()
        count_result.scalar_one.return_value = 3  # FREE limit = 3

        db.execute = AsyncMock(side_effect=[plan_result, count_result])

        with pytest.raises(ForbiddenError, match="项目上限"):
            await svc.check_project_limit(uuid.uuid4())


class TestCheckAiCallLimit:
    @patch("arc.application.billing.quota_service.settings")
    async def test_skips_in_debug_mode(self, mock_settings) -> None:
        mock_settings.debug = True
        svc, db = _make_service()

        await svc.check_ai_call_limit(uuid.uuid4())
        db.execute.assert_not_called()

    @patch("arc.application.billing.quota_service.settings")
    async def test_raises_when_exceeded(self, mock_settings) -> None:
        mock_settings.debug = False
        svc, db = _make_service()

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = "free"
        calls_result = MagicMock()
        calls_result.scalar_one_or_none.return_value = 50  # FREE limit = 50

        db.execute = AsyncMock(side_effect=[plan_result, calls_result])

        with pytest.raises(ForbiddenError, match="AI 调用上限"):
            await svc.check_ai_call_limit(uuid.uuid4())

    @patch("arc.application.billing.quota_service.settings")
    async def test_passes_when_no_usage_today(self, mock_settings) -> None:
        mock_settings.debug = False
        svc, db = _make_service()

        plan_result = MagicMock()
        plan_result.scalar_one_or_none.return_value = "free"
        calls_result = MagicMock()
        calls_result.scalar_one_or_none.return_value = None

        db.execute = AsyncMock(side_effect=[plan_result, calls_result])

        await svc.check_ai_call_limit(uuid.uuid4())


class TestIncrementAiCalls:
    async def test_increments_existing_record(self) -> None:
        svc, db = _make_service()

        existing_record = MagicMock()
        existing_record.ai_calls = 10
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_record
        db.execute = AsyncMock(return_value=mock_result)
        db.flush = AsyncMock()

        await svc.increment_ai_calls(uuid.uuid4(), count=3)

        assert existing_record.ai_calls == 13
        db.flush.assert_awaited_once()

    async def test_creates_new_record_when_none_exists(self) -> None:
        svc, db = _make_service()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)
        db.add = MagicMock()
        db.flush = AsyncMock()

        await svc.increment_ai_calls(uuid.uuid4(), count=1)

        db.add.assert_called_once()
        db.flush.assert_awaited_once()
