from __future__ import annotations

from enum import StrEnum


class AuthMethod(StrEnum):
    PASSWORD = "password"
    SMS = "sms"
    SSO = "sso"
