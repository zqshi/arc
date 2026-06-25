from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.organization.entity import Organization, OrganizationMember


class AbstractOrganizationRepository(ABC):
    """Domain-level contract for organization persistence."""

    @abstractmethod
    async def create(self, org: Organization) -> Organization: ...

    @abstractmethod
    async def get_by_id(self, org_id: uuid.UUID) -> Organization | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Organization | None: ...

    @abstractmethod
    async def update(self, org: Organization) -> None: ...


class AbstractOrganizationMemberRepository(ABC):
    """Domain-level contract for organization member persistence."""

    @abstractmethod
    async def add(self, member: OrganizationMember) -> OrganizationMember: ...

    @abstractmethod
    async def remove(self, org_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    @abstractmethod
    async def get_member(
        self, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None: ...

    @abstractmethod
    async def list_by_org(self, org_id: uuid.UUID) -> list[OrganizationMember]: ...

    @abstractmethod
    async def list_orgs_for_user(
        self, user_id: uuid.UUID
    ) -> list[OrganizationMember]: ...

    @abstractmethod
    async def count_members(self, org_id: uuid.UUID) -> int: ...
