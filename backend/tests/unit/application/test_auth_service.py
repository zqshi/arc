from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from arc.application.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
)
from arc.application.auth.password import hash_password, verify_password
from arc.domain.errors import AuthenticationError


@pytest.fixture(autouse=True)
def _debug_mode():
    with patch("arc.application.auth.jwt.settings") as mock_settings:
        mock_settings.debug = True
        mock_settings.jwt_secret = ""
        mock_settings.jwt_access_expire_minutes = 30
        mock_settings.jwt_refresh_expire_days = 7
        yield


class TestJWT:
    def test_create_and_verify_access_token(self):
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id, "testuser")
        payload = verify_access_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "access"
        assert payload["username"] == "testuser"

    def test_create_access_token_without_username(self):
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id)
        payload = verify_access_token(token)
        assert payload["sub"] == user_id
        assert "username" not in payload

    def test_create_and_verify_refresh_token(self):
        user_id = str(uuid.uuid4())
        token, jti = create_refresh_token(user_id)
        payload = verify_refresh_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token(str(uuid.uuid4()))
        with pytest.raises(AuthenticationError, match="类型错误"):
            verify_refresh_token(token)

    def test_refresh_token_rejected_as_access(self):
        token, _ = create_refresh_token(str(uuid.uuid4()))
        with pytest.raises(AuthenticationError, match="类型错误"):
            verify_access_token(token)

    def test_invalid_token_raises_error(self):
        with pytest.raises(AuthenticationError, match="无效"):
            verify_access_token("not-a-valid-token")

    def test_tampered_token_raises_error(self):
        token = create_access_token(str(uuid.uuid4()))
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(AuthenticationError):
            verify_access_token(tampered)


class TestPassword:
    def test_hash_and_verify(self):
        plain = "MyS3cur3P@ss!"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("correct-password")
        assert not verify_password("wrong-password", hashed)

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2  # bcrypt salt makes each hash unique


class TestRegistrationRole:
    """A1 投产门禁: 注册用户 role 由首用户特例决定 (系统无用户→首注册者 ADMIN)。"""

    @pytest.fixture
    def svc(self):
        from unittest.mock import MagicMock

        from arc.application.auth.service import AuthService

        s = AuthService(MagicMock())
        s.user_repo = MagicMock()
        s.org_svc = MagicMock()
        return s

    async def test_first_user_becomes_admin(self, svc):
        from unittest.mock import AsyncMock

        from arc.domain.user.value_objects import UserRole

        svc.user_repo.is_empty = AsyncMock(return_value=True)
        svc.user_repo.get_by_username = AsyncMock(return_value=None)
        svc.user_repo.create = AsyncMock(side_effect=lambda u: u)
        svc.org_svc.create_org = AsyncMock()
        user = await svc.register_with_password("alice", "pw123456", "Alice")
        assert user.role == UserRole.ADMIN

    async def test_non_first_user_becomes_member(self, svc):
        from unittest.mock import AsyncMock

        from arc.domain.user.value_objects import UserRole

        svc.user_repo.is_empty = AsyncMock(return_value=False)
        svc.user_repo.get_by_username = AsyncMock(return_value=None)
        svc.user_repo.create = AsyncMock(side_effect=lambda u: u)
        svc.org_svc.create_org = AsyncMock()
        user = await svc.register_with_password("bob", "pw123456", "Bob")
        assert user.role == UserRole.MEMBER

    async def test_first_phone_user_becomes_admin(self, svc):
        from unittest.mock import AsyncMock

        from arc.domain.user.value_objects import UserRole

        svc.user_repo.is_empty = AsyncMock(return_value=True)
        svc.user_repo.get_by_phone = AsyncMock(return_value=None)
        svc.user_repo.create = AsyncMock(side_effect=lambda u: u)
        svc.org_svc.create_org = AsyncMock()
        user = await svc.register_with_phone("13800138000", "Phone")
        assert user.role == UserRole.ADMIN


class TestChangeUserRole:
    """A1 投产门禁: admin 提权 + 最后 admin 保护。"""

    @pytest.fixture
    def svc(self):
        from unittest.mock import MagicMock

        from arc.application.auth.service import AuthService

        s = AuthService(MagicMock())
        s.user_repo = MagicMock()
        return s

    async def test_admin_can_promote_member(self, svc):
        from unittest.mock import AsyncMock

        from arc.domain.user.entity import User
        from arc.domain.user.value_objects import UserRole

        actor = User(display_name="Admin", role=UserRole.ADMIN)
        target = User(display_name="Bob", role=UserRole.MEMBER)
        svc.user_repo.get_by_id = AsyncMock(return_value=target)
        svc.user_repo.update = AsyncMock(side_effect=lambda u: u)
        result = await svc.change_user_role(target.id, UserRole.ADMIN, actor)
        assert result.role == UserRole.ADMIN

    async def test_non_admin_cannot_change_role(self, svc):
        from arc.domain.errors import ForbiddenError
        from arc.domain.user.entity import User
        from arc.domain.user.value_objects import UserRole

        actor = User(display_name="Member", role=UserRole.MEMBER)
        with pytest.raises(ForbiddenError):
            await svc.change_user_role(uuid.uuid4(), UserRole.ADMIN, actor)

    async def test_cannot_demote_last_admin(self, svc):
        from unittest.mock import AsyncMock

        from arc.domain.errors import ForbiddenError
        from arc.domain.user.entity import User
        from arc.domain.user.value_objects import UserRole

        actor = User(display_name="Admin", role=UserRole.ADMIN)
        target = User(display_name="Other", role=UserRole.ADMIN)
        svc.user_repo.get_by_id = AsyncMock(return_value=target)
        svc.user_repo.count_admins = AsyncMock(return_value=1)
        with pytest.raises(ForbiddenError):
            await svc.change_user_role(target.id, UserRole.MEMBER, actor)

    async def test_can_demote_when_multiple_admins(self, svc):
        from unittest.mock import AsyncMock

        from arc.domain.user.entity import User
        from arc.domain.user.value_objects import UserRole

        actor = User(display_name="Admin", role=UserRole.ADMIN)
        target = User(display_name="Other", role=UserRole.ADMIN)
        svc.user_repo.get_by_id = AsyncMock(return_value=target)
        svc.user_repo.count_admins = AsyncMock(return_value=2)
        svc.user_repo.update = AsyncMock(side_effect=lambda u: u)
        result = await svc.change_user_role(target.id, UserRole.MEMBER, actor)
        assert result.role == UserRole.MEMBER
