from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.errors import DomainError
from arc.domain.user.value_objects import UserRole


class UserError(DomainError):
    """用户域错误。"""
    pass


@dataclass
class User:
    display_name: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    username: str | None = None
    phone: str | None = None
    hashed_password: str | None = None
    is_active: bool = True
    role: UserRole = UserRole.MEMBER  # A1: 默认 MEMBER, 首用户特例/提权才 ADMIN (投产门禁)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # ─── 行为方法 ───────────────────────────────────────────

    def update_profile(self, *, display_name: str | None = None) -> None:
        """更新用户资料。"""
        if display_name is not None:
            if not display_name.strip():
                raise UserError("显示名称不能为空")
            self.display_name = display_name.strip()
        self.updated_at = datetime.now(UTC)

    def set_hashed_password(self, hashed: str) -> None:
        """设置已哈希的密码。明文哈希在 application 层完成。"""
        if not hashed:
            raise UserError("密码哈希不能为空")
        self.hashed_password = hashed
        self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        """停用账户。"""
        if not self.is_active:
            raise UserError("账户已处于停用状态")
        self.is_active = False
        self.updated_at = datetime.now(UTC)

    def reactivate(self) -> None:
        """重新激活账户。"""
        if self.is_active:
            raise UserError("账户已处于活跃状态")
        self.is_active = True
        self.updated_at = datetime.now(UTC)

    def change_role(self, new_role: UserRole) -> None:
        """变更用户角色。"""
        if new_role == self.role:
            return
        self.role = new_role
        self.updated_at = datetime.now(UTC)

    def has_permission(self, required_role: UserRole) -> bool:
        """检查用户是否具有指定角色的权限。

        权限层级: admin > member > viewer
        """
        hierarchy = {UserRole.VIEWER: 0, UserRole.MEMBER: 1, UserRole.ADMIN: 2}
        return hierarchy.get(self.role, 0) >= hierarchy.get(required_role, 0)

    def bind_phone(self, phone: str) -> None:
        """绑定手机号。"""
        if not phone or not phone.strip():
            raise UserError("手机号不能为空")
        self.phone = phone.strip()
        self.updated_at = datetime.now(UTC)
