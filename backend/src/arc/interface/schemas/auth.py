from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str | None = Field(None, min_length=3, max_length=50)
    phone: str | None = Field(None, pattern=r"^1[3-9]\d{9}$")
    password: str | None = Field(None, min_length=6, max_length=128)
    display_name: str | None = Field(None, max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class SMSSendRequest(BaseModel):
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")


class SMSLoginRequest(BaseModel):
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    code: str = Field(..., min_length=6, max_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserResponse | None = None


class UserResponse(BaseModel):
    id: str
    username: str | None
    phone: str | None
    display_name: str
