from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from arc.application.organization.service import OrganizationService
from arc.domain.errors import ConflictError, ForbiddenError, NotFoundError
from arc.domain.organization.value_objects import OrgPlan, OrgRole
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.organization import (
    CreateOrgRequest,
    InviteMemberRequest,
    OrgDetailResponse,
    OrgMemberResponse,
    OrgResponse,
    SwitchOrgRequest,
    UpdatePlanRequest,
)

router = APIRouter()


def _handle_domain_error(e: Exception):
    if isinstance(e, NotFoundError):
        raise HTTPException(404, str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(409, str(e))
    if isinstance(e, ForbiddenError):
        raise HTTPException(403, str(e))
    raise


@router.get("", response_model=list[OrgResponse])
async def list_my_orgs(user: CurrentUser, db: DbSession):
    svc = OrganizationService(db)
    return await svc.list_user_orgs(user.id)


@router.post("", response_model=OrgDetailResponse, status_code=201)
async def create_org(req: CreateOrgRequest, user: CurrentUser, db: DbSession):
    svc = OrganizationService(db)
    try:
        org = await svc.create_org(name=req.name, owner_id=user.id, slug=req.slug)
    except (ConflictError, ForbiddenError) as e:
        _handle_domain_error(e)
    return OrgDetailResponse(
        id=str(org.id), name=org.name, slug=org.slug,
        plan=org.plan.value, is_active=org.is_active,
    )


@router.get("/{org_id}", response_model=OrgDetailResponse)
async def get_org(org_id: UUID, user: CurrentUser, db: DbSession):
    svc = OrganizationService(db)
    try:
        org = await svc.get_org(org_id)
    except NotFoundError as e:
        _handle_domain_error(e)
    return OrgDetailResponse(
        id=str(org.id), name=org.name, slug=org.slug,
        plan=org.plan.value, is_active=org.is_active,
    )


@router.get("/{org_id}/members", response_model=list[OrgMemberResponse])
async def list_members(org_id: UUID, user: CurrentUser, db: DbSession):
    from arc.infrastructure.repositories.organization import OrganizationMemberRepository
    from arc.infrastructure.repositories.user import UserRepository

    member_repo = OrganizationMemberRepository(db)
    member = await member_repo.get_member(org_id, user.id)
    if not member:
        raise HTTPException(403, "非组织成员")

    members = await member_repo.list_by_org(org_id)
    user_repo = UserRepository(db)
    result = []
    for m in members:
        u = await user_repo.get_by_id(m.user_id)
        result.append(OrgMemberResponse(
            id=str(m.id),
            user_id=str(m.user_id),
            display_name=u.display_name if u else "未知用户",
            role=m.role.value,
        ))
    return result


@router.post("/{org_id}/members", response_model=OrgMemberResponse, status_code=201)
async def invite_member(
    org_id: UUID, req: InviteMemberRequest, user: CurrentUser, db: DbSession,
):
    svc = OrganizationService(db)
    try:
        member = await svc.invite_member(
            org_id=org_id,
            user_id=UUID(req.user_id),
            role=OrgRole(req.role),
            inviter_id=user.id,
        )
    except (NotFoundError, ConflictError, ForbiddenError) as e:
        _handle_domain_error(e)
    return OrgMemberResponse(
        id=str(member.id),
        user_id=str(member.user_id),
        display_name="",
        role=member.role.value,
    )


@router.delete("/{org_id}/members/{user_id}", status_code=204)
async def remove_member(org_id: UUID, user_id: UUID, user: CurrentUser, db: DbSession):
    svc = OrganizationService(db)
    try:
        await svc.remove_member(org_id=org_id, user_id=user_id, remover_id=user.id)
    except (NotFoundError, ForbiddenError) as e:
        _handle_domain_error(e)


@router.put("/{org_id}/plan", response_model=OrgDetailResponse)
async def update_plan(org_id: UUID, req: UpdatePlanRequest, user: CurrentUser, db: DbSession):
    svc = OrganizationService(db)
    try:
        org = await svc.update_plan(org_id=org_id, plan=OrgPlan(req.plan), user_id=user.id)
    except (NotFoundError, ForbiddenError) as e:
        _handle_domain_error(e)
    return OrgDetailResponse(
        id=str(org.id), name=org.name, slug=org.slug,
        plan=org.plan.value, is_active=org.is_active,
    )


@router.post("/switch", status_code=200)
async def switch_org(req: SwitchOrgRequest, user: CurrentUser, db: DbSession):
    from arc.application.auth.jwt import create_access_token
    from arc.infrastructure.repositories.organization import OrganizationMemberRepository

    member_repo = OrganizationMemberRepository(db)
    member = await member_repo.get_member(UUID(req.org_id), user.id)
    if not member:
        raise HTTPException(403, "非该组织成员")

    access_token = create_access_token(
        str(user.id), user.username, org_id=req.org_id,
    )
    return {"access_token": access_token, "org_id": req.org_id}
