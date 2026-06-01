"""Tests for domain/organization entities."""

import uuid

from arc.domain.organization.entity import Organization, OrganizationMember
from arc.domain.organization.value_objects import OrgPlan, OrgRole


class TestOrganization:
    def test_creation_defaults(self):
        org = Organization(name="Test Org")
        assert org.plan == OrgPlan.FREE
        assert org.is_active is True

    def test_upgrade_plan(self):
        org = Organization(name="Test")
        org.upgrade_plan(OrgPlan.PRO)
        assert org.plan == OrgPlan.PRO

    def test_deactivate(self):
        org = Organization(name="Test")
        org.deactivate()
        assert org.is_active is False

    def test_get_limit(self):
        org = Organization(name="Test", plan=OrgPlan.FREE)
        limit = org.get_limit("max_projects")
        assert isinstance(limit, int)


class TestOrganizationMember:
    def test_creation_defaults(self):
        m = OrganizationMember(organization_id=uuid.uuid4(), user_id=uuid.uuid4())
        assert m.role == OrgRole.MEMBER
        assert m.is_owner is False

    def test_owner_role(self):
        m = OrganizationMember(organization_id=uuid.uuid4(), user_id=uuid.uuid4(), role=OrgRole.OWNER)
        assert m.is_owner is True
        assert m.is_admin_or_above is True

    def test_admin_role(self):
        m = OrganizationMember(organization_id=uuid.uuid4(), user_id=uuid.uuid4(), role=OrgRole.ADMIN)
        assert m.is_owner is False
        assert m.is_admin_or_above is True

    def test_member_role(self):
        m = OrganizationMember(organization_id=uuid.uuid4(), user_id=uuid.uuid4(), role=OrgRole.MEMBER)
        assert m.is_admin_or_above is False
