"""Tests for domain/user/value_objects.py — enum completeness."""

from arc.domain.user.value_objects import AuthMethod, UserRole


class TestAuthMethod:
    def test_enum_values(self):
        assert AuthMethod.PASSWORD == "password"
        assert AuthMethod.SMS == "sms"
        assert AuthMethod.SSO == "sso"

    def test_enum_count(self):
        assert len(AuthMethod) == 3


class TestUserRole:
    def test_enum_values(self):
        assert UserRole.ADMIN == "admin"
        assert UserRole.MEMBER == "member"
        assert UserRole.VIEWER == "viewer"

    def test_enum_count(self):
        assert len(UserRole) == 3

    def test_str_equality(self):
        assert UserRole("admin") == UserRole.ADMIN
