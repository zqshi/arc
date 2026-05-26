from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from arc.config import settings
from arc.domain.errors import AuthenticationError

ALGORITHM = "HS256"


def _get_secret() -> str:
    secret = settings.jwt_secret
    if not secret:
        if not settings.debug:
            raise RuntimeError(
                "ARC_JWT_SECRET must be set in production. "
                "Set ARC_DEBUG=true for local development with a default secret."
            )
        secret = "arc-dev-secret-do-not-use-in-production"
        logging.getLogger(__name__).warning("Using insecure default JWT secret (debug mode)")
    return secret


def create_access_token(
    user_id: str, username: str | None = None, org_id: str | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_expire_minutes)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
    }
    if username:
        payload["username"] = username
    if org_id:
        payload["org_id"] = org_id
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Returns (token_string, jti)."""
    jti = uuid.uuid4().hex
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "exp": expire,
    }
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM), jti


def verify_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
    except JWTError as e:
        raise AuthenticationError(f"Token 无效: {e}")
    if payload.get("type") != "access":
        raise AuthenticationError("Token 类型错误")
    return payload


def verify_refresh_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
    except JWTError as e:
        raise AuthenticationError(f"Refresh token 无效: {e}")
    if payload.get("type") != "refresh":
        raise AuthenticationError("Token 类型错误")
    return payload
