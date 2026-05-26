from __future__ import annotations

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.errors import ConflictError, ForbiddenError, NotFoundError
from arc.domain.organization.entity import Organization, OrganizationMember
from arc.domain.organization.value_objects import OrgPlan, OrgRole
from arc.infrastructure.repositories.organization import (
    OrganizationMemberRepository,
    OrganizationRepository,
)


class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.org_repo = OrganizationRepository(db)
        self.member_repo = OrganizationMemberRepository(db)

    async def create_org(
        self,
        name: str,
        owner_id: uuid.UUID,
        slug: str | None = None,
    ) -> Organization:
        slug = slug or self._slugify(name)
        existing = await self.org_repo.get_by_slug(slug)
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

        org = Organization(name=name, slug=slug)
        org = await self.org_repo.create(org)

        owner = OrganizationMember(
            organization_id=org.id,
            user_id=owner_id,
            role=OrgRole.OWNER,
        )
        await self.member_repo.add(owner)
        return org

    async def get_org(self, org_id: uuid.UUID) -> Organization:
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("组织不存在")
        return org

    async def list_user_orgs(self, user_id: uuid.UUID) -> list[dict]:
        memberships = await self.member_repo.list_orgs_for_user(user_id)
        result = []
        for m in memberships:
            org = await self.org_repo.get_by_id(m.organization_id)
            if org and org.is_active:
                result.append({
                    "id": str(org.id),
                    "name": org.name,
                    "slug": org.slug,
                    "plan": org.plan.value,
                    "role": m.role.value,
                })
        return result

    async def invite_member(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        role: OrgRole = OrgRole.MEMBER,
        inviter_id: uuid.UUID | None = None,
    ) -> OrganizationMember:
        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("组织不存在")

        if inviter_id:
            inviter = await self.member_repo.get_member(org_id, inviter_id)
            if not inviter or not inviter.is_admin_or_above:
                raise ForbiddenError("仅管理员可邀请成员")

        existing = await self.member_repo.get_member(org_id, user_id)
        if existing:
            raise ConflictError("该用户已是组织成员")

        limit = org.get_limit("max_members")
        current = await self.member_repo.count_members(org_id)
        if current >= limit:
            raise ForbiddenError(f"当前套餐最多 {limit} 名成员, 请升级")

        member = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            role=role,
        )
        return await self.member_repo.add(member)

    async def remove_member(
        self,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        remover_id: uuid.UUID,
    ) -> None:
        remover = await self.member_repo.get_member(org_id, remover_id)
        if not remover or not remover.is_admin_or_above:
            raise ForbiddenError("仅管理员可移除成员")

        target = await self.member_repo.get_member(org_id, user_id)
        if not target:
            raise NotFoundError("成员不存在")
        if target.is_owner:
            raise ForbiddenError("不能移除组织所有者")

        await self.member_repo.remove(org_id, user_id)

    async def update_plan(
        self,
        org_id: uuid.UUID,
        plan: OrgPlan,
        user_id: uuid.UUID,
    ) -> Organization:
        member = await self.member_repo.get_member(org_id, user_id)
        if not member or not member.is_owner:
            raise ForbiddenError("仅所有者可变更套餐")

        org = await self.org_repo.get_by_id(org_id)
        if not org:
            raise NotFoundError("组织不存在")

        org.upgrade_plan(plan)
        await self.org_repo.update(org)
        return org

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9\s-]", "", name.lower().strip())
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug or f"org-{uuid.uuid4().hex[:8]}"
