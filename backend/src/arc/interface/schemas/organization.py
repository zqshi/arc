from __future__ import annotations

from pydantic import BaseModel, Field


class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(None, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")


class InviteMemberRequest(BaseModel):
    user_id: str
    role: str = Field("member", pattern=r"^(admin|member)$")


class UpdatePlanRequest(BaseModel):
    plan: str = Field(..., pattern=r"^(free|pro|team)$")


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    role: str


class OrgDetailResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    is_active: bool


class OrgMemberResponse(BaseModel):
    id: str
    user_id: str
    display_name: str
    role: str


class SwitchOrgRequest(BaseModel):
    org_id: str
