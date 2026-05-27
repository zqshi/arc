from __future__ import annotations

import uuid

from arc.domain.user.entity import User
from arc.domain.user.value_objects import UserRole


class TestUserCreation:
    def test_defaults(self) -> None:
        u = User(display_name="Alice")
        assert u.display_name == "Alice"
        assert u.role == UserRole.ADMIN
        assert u.is_active is True
        assert u.username is None
        assert u.phone is None
        assert u.hashed_password is None

    def test_full_fields(self) -> None:
        uid = uuid.uuid4()
        u = User(
            display_name="Bob",
            id=uid,
            username="bob",
            phone="13800138000",
            hashed_password="hashed_abc",
            is_active=False,
            role=UserRole.MEMBER,
        )
        assert u.id == uid
        assert u.username == "bob"
        assert u.phone == "13800138000"
        assert u.role == UserRole.MEMBER
        assert u.is_active is False


class TestUserRoleValues:
    def test_all_roles(self) -> None:
        assert UserRole.ADMIN == "admin"
        assert UserRole.MEMBER == "member"
        assert UserRole.VIEWER == "viewer"
