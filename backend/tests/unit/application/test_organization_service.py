from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.organization.service import OrganizationService
from arc.domain.errors import ConflictError, ForbiddenError, NotFoundError
from arc.domain.organization.entity import Organization, OrganizationMember
from arc.domain.organization.value_objects import OrgPlan, OrgRole


@pytest.fixture
def svc():
    db = AsyncMock()
    service = OrganizationService(db)
    service.org_repo = AsyncMock()
    service.member_repo = AsyncMock()
    return service


@pytest.fixture
def sample_org():
    return Organization(name="Test Org", slug="test-org", id=uuid.uuid4())


@pytest.fixture
def owner_member(sample_org):
    return OrganizationMember(
        organization_id=sample_org.id,
        user_id=uuid.uuid4(),
        role=OrgRole.OWNER,
    )


class TestCreateOrg:
    async def test_creates_org_and_owner(self, svc):
        svc.org_repo.get_by_slug.return_value = None
        svc.org_repo.create.side_effect = lambda o: o
        svc.member_repo.add.side_effect = lambda m: m

        user_id = uuid.uuid4()
        org = await svc.create_org("My Workspace", owner_id=user_id)

        assert org.name == "My Workspace"
        svc.member_repo.add.assert_called_once()
        member_arg = svc.member_repo.add.call_args[0][0]
        assert member_arg.role == OrgRole.OWNER
        assert member_arg.user_id == user_id

    async def test_slug_collision_gets_suffix(self, svc):
        existing = Organization(name="Existing", slug="my-workspace")
        svc.org_repo.get_by_slug.return_value = existing
        svc.org_repo.create.side_effect = lambda o: o
        svc.member_repo.add.side_effect = lambda m: m

        org = await svc.create_org("My Workspace", owner_id=uuid.uuid4())
        assert org.slug != "my-workspace"
        assert org.slug.startswith("my-workspace-")


class TestInviteMember:
    async def test_invite_by_admin(self, svc, sample_org):
        svc.org_repo.get_by_id.return_value = sample_org
        svc.member_repo.get_member.side_effect = [
            OrganizationMember(
                organization_id=sample_org.id,
                user_id=uuid.uuid4(),
                role=OrgRole.ADMIN,
            ),
            None,
        ]
        svc.member_repo.count_members.return_value = 0
        svc.member_repo.add.side_effect = lambda m: m

        member = await svc.invite_member(
            sample_org.id,
            user_id=uuid.uuid4(),
            inviter_id=uuid.uuid4(),
        )
        assert member.role == OrgRole.MEMBER

    async def test_invite_by_non_admin_forbidden(self, svc, sample_org):
        svc.org_repo.get_by_id.return_value = sample_org
        svc.member_repo.get_member.return_value = OrganizationMember(
            organization_id=sample_org.id,
            user_id=uuid.uuid4(),
            role=OrgRole.MEMBER,
        )
        with pytest.raises(ForbiddenError, match="管理员"):
            await svc.invite_member(
                sample_org.id,
                user_id=uuid.uuid4(),
                inviter_id=uuid.uuid4(),
            )

    async def test_invite_duplicate_conflict(self, svc, sample_org):
        svc.org_repo.get_by_id.return_value = sample_org
        existing_member = OrganizationMember(
            organization_id=sample_org.id,
            user_id=uuid.uuid4(),
            role=OrgRole.ADMIN,
        )
        target = OrganizationMember(
            organization_id=sample_org.id,
            user_id=uuid.uuid4(),
            role=OrgRole.MEMBER,
        )
        svc.member_repo.get_member.side_effect = [existing_member, target]
        with pytest.raises(ConflictError):
            await svc.invite_member(
                sample_org.id,
                user_id=target.user_id,
                inviter_id=existing_member.user_id,
            )

    async def test_invite_exceeds_plan_limit(self, svc, sample_org):
        svc.org_repo.get_by_id.return_value = sample_org
        admin = OrganizationMember(
            organization_id=sample_org.id,
            user_id=uuid.uuid4(),
            role=OrgRole.ADMIN,
        )
        svc.member_repo.get_member.side_effect = [admin, None]
        svc.member_repo.count_members.return_value = 1

        with pytest.raises(ForbiddenError, match="升级"):
            await svc.invite_member(
                sample_org.id,
                user_id=uuid.uuid4(),
                inviter_id=admin.user_id,
            )


class TestRemoveMember:
    async def test_remove_member_by_admin(self, svc, sample_org):
        admin = OrganizationMember(
            organization_id=sample_org.id,
            user_id=uuid.uuid4(),
            role=OrgRole.ADMIN,
        )
        target = OrganizationMember(
            organization_id=sample_org.id,
            user_id=uuid.uuid4(),
            role=OrgRole.MEMBER,
        )
        svc.member_repo.get_member.side_effect = [admin, target]
        svc.member_repo.remove.return_value = True

        await svc.remove_member(sample_org.id, target.user_id, admin.user_id)
        svc.member_repo.remove.assert_called_once()

    async def test_cannot_remove_owner(self, svc, sample_org):
        admin = OrganizationMember(
            organization_id=sample_org.id,
            user_id=uuid.uuid4(),
            role=OrgRole.ADMIN,
        )
        owner = OrganizationMember(
            organization_id=sample_org.id,
            user_id=uuid.uuid4(),
            role=OrgRole.OWNER,
        )
        svc.member_repo.get_member.side_effect = [admin, owner]

        with pytest.raises(ForbiddenError, match="所有者"):
            await svc.remove_member(sample_org.id, owner.user_id, admin.user_id)


class TestUpdatePlan:
    async def test_owner_can_upgrade(self, svc, sample_org):
        owner_id = uuid.uuid4()
        svc.member_repo.get_member.return_value = OrganizationMember(
            organization_id=sample_org.id,
            user_id=owner_id,
            role=OrgRole.OWNER,
        )
        svc.org_repo.get_by_id.return_value = sample_org
        svc.org_repo.update.return_value = None

        org = await svc.update_plan(sample_org.id, OrgPlan.PRO, owner_id)
        assert org.plan == OrgPlan.PRO

    async def test_non_owner_forbidden(self, svc, sample_org):
        svc.member_repo.get_member.return_value = OrganizationMember(
            organization_id=sample_org.id,
            user_id=uuid.uuid4(),
            role=OrgRole.ADMIN,
        )
        with pytest.raises(ForbiddenError):
            await svc.update_plan(sample_org.id, OrgPlan.TEAM, uuid.uuid4())


class TestSlugify:
    def test_basic(self):
        assert OrganizationService._slugify("My Team") == "my-team"

    def test_chinese(self):
        slug = OrganizationService._slugify("测试团队")
        assert slug.startswith("org-")

    def test_special_chars(self):
        assert OrganizationService._slugify("Hello World!!!") == "hello-world"
