from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.organization.entity import Organization, OrganizationMember
from arc.domain.organization.repository import (
    AbstractOrganizationMemberRepository,
    AbstractOrganizationRepository,
)
from arc.domain.organization.value_objects import OrgPlan, OrgRole
from arc.infrastructure.models.organization import OrganizationMemberModel, OrganizationModel


class OrganizationRepository(AbstractOrganizationRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, org: Organization) -> Organization:
        model = OrganizationModel(
            id=org.id,
            name=org.name,
            slug=org.slug,
            plan=org.plan.value,
            is_active=org.is_active,
        )
        self.db.add(model)
        await self.db.flush()
        return org

    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None:
        result = await self.db.execute(
            select(OrganizationModel).where(OrganizationModel.id == org_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self.db.execute(
            select(OrganizationModel).where(OrganizationModel.slug == slug)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def update(self, org: Organization) -> None:
        result = await self.db.execute(
            select(OrganizationModel).where(OrganizationModel.id == org.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return
        model.name = org.name
        model.slug = org.slug
        model.plan = org.plan.value
        model.is_active = org.is_active
        await self.db.flush()

    @staticmethod
    def _to_entity(model: OrganizationModel) -> Organization:
        return Organization(
            id=model.id,
            name=model.name,
            slug=model.slug,
            plan=OrgPlan(model.plan),
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class OrganizationMemberRepository(AbstractOrganizationMemberRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add(self, member: OrganizationMember) -> OrganizationMember:
        model = OrganizationMemberModel(
            id=member.id,
            organization_id=member.organization_id,
            user_id=member.user_id,
            role=member.role.value,
        )
        self.db.add(model)
        await self.db.flush()
        return member

    async def remove(self, org_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self.db.execute(
            select(OrganizationMemberModel).where(
                OrganizationMemberModel.organization_id == org_id,
                OrganizationMemberModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.db.delete(model)
        await self.db.flush()
        return True

    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        result = await self.db.execute(
            select(OrganizationMemberModel).where(
                OrganizationMemberModel.organization_id == org_id,
                OrganizationMemberModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_by_org(self, org_id: uuid.UUID) -> list[OrganizationMember]:
        result = await self.db.execute(
            select(OrganizationMemberModel)
            .where(OrganizationMemberModel.organization_id == org_id)
            .order_by(OrganizationMemberModel.created_at)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def list_orgs_for_user(self, user_id: uuid.UUID) -> list[OrganizationMember]:
        result = await self.db.execute(
            select(OrganizationMemberModel)
            .where(OrganizationMemberModel.user_id == user_id)
            .order_by(OrganizationMemberModel.created_at)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def count_members(self, org_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(OrganizationMemberModel)
            .where(OrganizationMemberModel.organization_id == org_id)
        )
        return result.scalar_one()

    @staticmethod
    def _to_entity(model: OrganizationMemberModel) -> OrganizationMember:
        return OrganizationMember(
            id=model.id,
            organization_id=model.organization_id,
            user_id=model.user_id,
            role=OrgRole(model.role),
            created_at=model.created_at,
        )
