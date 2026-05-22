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
        token = create_refresh_token(user_id)
        payload = verify_refresh_token(token)
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_access_token_rejected_as_refresh(self):
        token = create_access_token(str(uuid.uuid4()))
        with pytest.raises(AuthenticationError, match="类型错误"):
            verify_refresh_token(token)

    def test_refresh_token_rejected_as_access(self):
        token = create_refresh_token(str(uuid.uuid4()))
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
