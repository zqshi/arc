from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from arc.application.billing.quota_service import QuotaService
from arc.interface.deps import CurrentOrgId, CurrentUser, DbSession

router = APIRouter()


class UsageResponse(BaseModel):
    plan: str
    projects_used: int
    projects_limit: int
    members_used: int
    members_limit: int
    ai_calls_today: int
    ai_calls_limit: int


class PlanLimitsResponse(BaseModel):
    free: dict[str, int]
    pro: dict[str, int]
    team: dict[str, int]


@router.get("/usage", response_model=UsageResponse)
async def get_usage(user: CurrentUser, db: DbSession, org_id: CurrentOrgId = None):
    if not org_id:
        raise HTTPException(400, "未关联组织")
    svc = QuotaService(db)
    summary = await svc.get_usage_summary(org_id)
    return UsageResponse(
        plan=summary.plan,
        projects_used=summary.projects_used,
        projects_limit=summary.projects_limit,
        members_used=summary.members_used,
        members_limit=summary.members_limit,
        ai_calls_today=summary.ai_calls_today,
        ai_calls_limit=summary.ai_calls_limit,
    )


@router.get("/plans", response_model=PlanLimitsResponse)
async def get_plan_limits():
    from arc.domain.organization.value_objects import PLAN_LIMITS, OrgPlan
    return PlanLimitsResponse(
        free=PLAN_LIMITS[OrgPlan.FREE],
        pro=PLAN_LIMITS[OrgPlan.PRO],
        team=PLAN_LIMITS[OrgPlan.TEAM],
    )
