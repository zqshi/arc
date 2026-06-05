"""原型预览编排 — 版本解析、状态查询、预览内容获取。

工程模式下，预览直接 redirect 到已部署的 URL。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from arc.infrastructure.repositories.project import VersionRepository

logger = logging.getLogger(__name__)


@dataclass
class PrototypeStatus:
    """原型状态查询结果。"""

    has_prototype: bool
    preview_url: str | None
    total_pages: int
    version_id: str | None


@dataclass
class PreviewResult:
    """预览内容获取结果。"""

    type: str  # "redirect" | "empty"
    content: str = ""  # URL for redirect, project name for empty


class PrototypePreviewService:
    """编排原型预览相关的版本解析和内容获取逻辑。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._version_repo = VersionRepository(db)

    async def resolve_active_version_id(
        self,
        project_id: uuid.UUID,
        explicit_version_id: str | None = None,
    ) -> uuid.UUID | None:
        """解析目标版本 ID。

        优先级: 显式指定 > 当前 active 版本 > released 版本 > None
        """
        if explicit_version_id:
            return uuid.UUID(explicit_version_id)

        versions = await self._version_repo.list_by_project(project_id)

        for v in versions:
            if v.status.value == "active":
                return v.id

        for v in versions:
            if v.status.value in ("released", "active"):
                return v.id

        return None

    async def get_prototype_status(
        self,
        project_id: uuid.UUID,
        version_id: str | None = None,
    ) -> PrototypeStatus:
        """检查项目/版本是否有可预览的原型。"""
        from arc.application.artifact.prototype_bundle import PrototypeBundleService

        vid = await self.resolve_active_version_id(project_id, version_id)

        svc = PrototypeBundleService(self._db)
        bundle = await svc.build_bundle(project_id, version_id=vid)

        return PrototypeStatus(
            has_prototype=bool(bundle.preview_url),
            preview_url=bundle.preview_url or None,
            total_pages=bundle.total_pages,
            version_id=str(vid) if vid else None,
        )

    async def authenticate_by_token(self, token: str) -> uuid.UUID | None:
        """通过 query token 认证用户，返回 user_id 或 None。"""
        try:
            from arc.application.auth.jwt import verify_access_token
            from arc.infrastructure.repositories.user import UserRepository

            payload = verify_access_token(token)
            user = await UserRepository(self._db).get_by_id(uuid.UUID(payload["sub"]))
            if user and user.is_active:
                return user.id
        except Exception:
            pass
        return None

    async def get_preview_content(
        self,
        project_id: uuid.UUID,
        project_local_path: str | None,
        project_name: str,
        version_id: str | None = None,
    ) -> PreviewResult:
        """获取预览内容。

        工程模式下直接 redirect 到已部署的 URL。

        优先级:
        1. prototype artifact 有 preview_url → redirect
        2. 版本有 prototype_preview_url → redirect
        3. 空状态
        """
        from arc.application.artifact.prototype_bundle import PrototypeBundleService

        vid = await self.resolve_active_version_id(project_id, version_id)

        # 优先级 1: prototype artifact 的 preview_url
        svc = PrototypeBundleService(self._db)
        bundle = await svc.build_bundle(project_id, version_id=vid)
        if bundle.preview_url:
            return PreviewResult(type="redirect", content=bundle.preview_url)

        # 优先级 2: 版本级 prototype_preview_url
        if vid:
            version = await self._version_repo.get_by_id(vid)
            if version and version.prototype_preview_url:
                url = version.prototype_preview_url
                if url.startswith("http://") or url.startswith("https://"):
                    return PreviewResult(type="redirect", content=url)

        # 空状态
        return PreviewResult(type="empty", content=project_name)
