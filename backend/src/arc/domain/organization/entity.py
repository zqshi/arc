from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.organization.value_objects import PLAN_LIMITS, OrgPlan, OrgRole


@dataclass
class Organization:
    name: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    slug: str = ""
    plan: OrgPlan = OrgPlan.FREE
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def upgrade_plan(self, plan: OrgPlan) -> None:
        self.plan = plan
        self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        self.is_active = False
        self.updated_at = datetime.now(UTC)

    def get_limit(self, key: str) -> int:
        return PLAN_LIMITS[self.plan].get(key, 0)


@dataclass
class OrganizationMember:
    organization_id: uuid.UUID
    user_id: uuid.UUID
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    role: OrgRole = OrgRole.MEMBER
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_owner(self) -> bool:
        return self.role == OrgRole.OWNER

    @property
    def is_admin_or_above(self) -> bool:
        return self.role in (OrgRole.OWNER, OrgRole.ADMIN)
