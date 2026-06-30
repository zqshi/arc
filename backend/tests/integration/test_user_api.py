"""A1 投产门禁: 用户角色管理 API 集成测试。

覆盖: admin 提权 / 非 admin 拒绝 (403) / 不存在用户 (404)。
最后 admin 保护由 unit (test_auth_service.TestChangeUserRole) 覆盖, 此处不依赖 DB 真实 admin 计数。
"""
from __future__ import annotations

import uuid


class TestUserRoleApi:
    """PATCH /api/users/{id}/role 权限边界。"""

    async def _override_current_user(self, user):
        from arc.interface.deps import get_current_user
        from arc.main import app

        async def _u():
            return user

        app.dependency_overrides[get_current_user] = _u

    async def test_admin_can_promote_member(self, client, db_session):
        from arc.application.auth.service import AuthService
        from arc.domain.user.entity import User
        from arc.domain.user.value_objects import UserRole

        svc = AuthService(db_session)
        target = await svc.register_with_password(
            f"u_{uuid.uuid4().hex[:6]}", "pw123456", "Promotee"
        )
        assert target.role == UserRole.MEMBER  # 非首用户 → member

        admin = User(id=uuid.uuid4(), display_name="Admin", role=UserRole.ADMIN)
        await self._override_current_user(admin)

        resp = await client.patch(f"/api/users/{target.id}/role", json={"role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    async def test_non_admin_rejected_403(self, client):
        from arc.domain.user.entity import User
        from arc.domain.user.value_objects import UserRole

        member = User(id=uuid.uuid4(), display_name="M", role=UserRole.MEMBER)
        await self._override_current_user(member)

        resp = await client.patch(f"/api/users/{uuid.uuid4()}/role", json={"role": "admin"})
        assert resp.status_code == 403

    async def test_unknown_user_404(self, client):
        from arc.domain.user.entity import User
        from arc.domain.user.value_objects import UserRole

        admin = User(id=uuid.uuid4(), display_name="Admin", role=UserRole.ADMIN)
        await self._override_current_user(admin)

        resp = await client.patch(f"/api/users/{uuid.uuid4()}/role", json={"role": "admin"})
        assert resp.status_code == 404
