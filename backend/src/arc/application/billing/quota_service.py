from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.config import settings
from arc.domain.errors import ForbiddenError
from arc.domain.organization.value_objects import PLAN_LIMITS, OrgPlan
from arc.infrastructure.models.billing import UsageDailyModel
from arc.infrastructure.models.organization import OrganizationModel
from arc.infrastructure.models.project import ProjectModel
from arc.infrastructure.models.todo import Todo as TodoModel


@dataclass
class UsageSummary:
    plan: str
    projects_used: int
    projects_limit: int
    members_used: int
    members_limit: int
    ai_calls_today: int
    ai_calls_limit: int


class QuotaService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_org_plan(self, org_id: uuid.UUID) -> OrgPlan:
        result = await self.db.execute(
            select(OrganizationModel.plan).where(OrganizationModel.id == org_id)
        )
        plan_str = result.scalar_one_or_none()
        return OrgPlan(plan_str) if plan_str else OrgPlan.FREE

    async def check_project_limit(self, org_id: uuid.UUID) -> None:
        if settings.debug:
            return
        plan = await self.get_org_plan(org_id)
        limit = PLAN_LIMITS[plan]["max_projects"]
        result = await self.db.execute(
            select(func.count())
            .select_from(ProjectModel)
            .where(ProjectModel.organization_id == org_id)
        )
        current = result.scalar_one()
        if current >= limit:
            raise ForbiddenError(
                f"已达 {plan.value} 套餐项目上限({limit}个)，请升级套餐"
            )

    async def check_todo_limit(self, org_id: uuid.UUID, project_id: uuid.UUID) -> None:
        if settings.debug:
            return
        plan = await self.get_org_plan(org_id)
        limit = PLAN_LIMITS[plan]["max_todos_per_project"]
        result = await self.db.execute(
            select(func.count())
            .select_from(TodoModel)
            .where(TodoModel.project_id == project_id)
        )
        current = result.scalar_one()
        if current >= limit:
            raise ForbiddenError(
                f"已达 {plan.value} 套餐单项目需求上限({limit}个)，请升级套餐"
            )

    async def check_ai_call_limit(self, org_id: uuid.UUID) -> None:
        if settings.debug:
            return
        plan = await self.get_org_plan(org_id)
        limit = PLAN_LIMITS[plan]["max_ai_calls_per_day"]
        today = date.today()
        result = await self.db.execute(
            select(UsageDailyModel.ai_calls).where(
                UsageDailyModel.organization_id == org_id,
                UsageDailyModel.usage_date == today,
            )
        )
        current = result.scalar_one_or_none() or 0
        if current >= limit:
            raise ForbiddenError(
                f"已达 {plan.value} 套餐每日 AI 调用上限({limit}次)，请升级套餐"
            )

    async def increment_ai_calls(self, org_id: uuid.UUID, count: int = 1) -> None:
        today = date.today()
        result = await self.db.execute(
            select(UsageDailyModel).where(
                UsageDailyModel.organization_id == org_id,
                UsageDailyModel.usage_date == today,
            )
        )
        record = result.scalar_one_or_none()
        if record:
            record.ai_calls += count
        else:
            self.db.add(UsageDailyModel(
                organization_id=org_id,
                usage_date=today,
                ai_calls=count,
            ))
        await self.db.flush()

    async def get_usage_summary(self, org_id: uuid.UUID) -> UsageSummary:
        plan = await self.get_org_plan(org_id)
        limits = PLAN_LIMITS[plan]

        projects_result = await self.db.execute(
            select(func.count())
            .select_from(ProjectModel)
            .where(ProjectModel.organization_id == org_id)
        )
        projects_used = projects_result.scalar_one()

        from arc.infrastructure.models.organization import OrganizationMemberModel
        members_result = await self.db.execute(
            select(func.count())
            .select_from(OrganizationMemberModel)
            .where(OrganizationMemberModel.organization_id == org_id)
        )
        members_used = members_result.scalar_one()

        today = date.today()
        ai_result = await self.db.execute(
            select(UsageDailyModel.ai_calls).where(
                UsageDailyModel.organization_id == org_id,
                UsageDailyModel.usage_date == today,
            )
        )
        ai_calls_today = ai_result.scalar_one_or_none() or 0

        return UsageSummary(
            plan=plan.value,
            projects_used=projects_used,
            projects_limit=limits["max_projects"],
            members_used=members_used,
            members_limit=limits["max_members"],
            ai_calls_today=ai_calls_today,
            ai_calls_limit=limits["max_ai_calls_per_day"],
        )
