"""原型工程聚合 — 查询项目/版本下的原型部署状态和预览 URL。

工程模式下，prototype artifact 包含 build 产物的部署信息，
不再需要聚合 HTML 片段。本模块简化为查询已部署的原型 URL 和路由表。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.artifact.value_objects import ArtifactType
from arc.infrastructure.repositories.artifact import ArtifactRepository

logger = logging.getLogger(__name__)


@dataclass
class PrototypeRoute:
    """原型中的单个路由。"""

    path: str
    name: str
    component: str = ""


@dataclass
class PrototypeBundle:
    """项目级原型聚合结果。"""

    preview_url: str = ""
    routes: list[PrototypeRoute] = field(default_factory=list)
    total_pages: int = 0
    tech_stack: str = ""
    build_status: str = ""
    project_dir: str = ""


class PrototypeBundleService:
    """查询项目/版本下原型工程的部署状态。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._artifact_repo = ArtifactRepository(db)

    async def build_bundle(
        self,
        project_id: uuid.UUID,
        *,
        version_id: uuid.UUID | None = None,
        current_todo_id: uuid.UUID | None = None,
    ) -> PrototypeBundle:
        """查询项目/版本的原型工程状态。

        按创建时间倒序，取最新的 prototype artifact。
        工程模式下 artifact content 包含 preview_url, routes, build_status 等。
        """
        if version_id:
            artifacts = await self._artifact_repo.list_by_version_and_type(
                version_id, ArtifactType.PROTOTYPE
            )
        else:
            artifacts = await self._artifact_repo.list_by_project_and_type(
                project_id, ArtifactType.PROTOTYPE
            )

        if not artifacts:
            return PrototypeBundle()

        # 取最新的 prototype artifact（按创建时间倒序）
        sorted_arts = sorted(artifacts, key=lambda a: a.created_at, reverse=True)

        for art in sorted_arts:
            content = art.content or {}

            # 工程模式：有 project_dir 字段
            if content.get("project_dir"):
                routes = [
                    PrototypeRoute(
                        path=r.get("path", "/"),
                        name=r.get("name", ""),
                        component=r.get("component", ""),
                    )
                    for r in content.get("routes", [])
                ]
                return PrototypeBundle(
                    preview_url=content.get("preview_url", ""),
                    routes=routes,
                    total_pages=len(routes),
                    tech_stack=content.get("tech_stack", ""),
                    build_status=content.get("build_status", ""),
                    project_dir=content.get("project_dir", ""),
                )

        return PrototypeBundle()
