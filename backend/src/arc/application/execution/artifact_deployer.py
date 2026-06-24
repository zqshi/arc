"""原型部署逻辑 — 从 artifact_extractor.py 提取。

职责：
- 检测 prototype artifact 是否为 SPA 工程
- 触发 DeployService 上传 dist/ 到 S3
- S3 未配置时 fallback 到本地 symlink serve
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.artifact.value_objects import ArtifactType
from arc.infrastructure.repositories.artifact import ArtifactRepository

logger = logging.getLogger(__name__)


def resolve_deploy_config(project_type, content, artifact_path):
    """按 project_type 解析部署配置 (断点D 修复)。

    BINARY_APP 用类型默认 (cargo tauri build + bundle), 不信 content 的 build_command
    (content 可能是前端 web 资源的 npm run build, 非原生构建命令);
    其他类型沿用 content (兼容 STATIC_SITE 既有行为)。

    DeployService 内部按 project_type 选 deployer: BINARY_APP → BinaryArtifactDeployer。
    """
    from arc.domain.deployment.value_objects import DeployConfig
    from arc.domain.project.value_objects import ProjectType

    if project_type == ProjectType.BINARY_APP:
        return DeployConfig.for_type(project_type)
    return DeployConfig(
        build_command=content.get("build_command", "npm run build"),
        artifact_path=artifact_path,
    )


class PrototypeDeployer:
    """原型部署器 — 将构建产物部署到 S3 或本地 serve。"""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._artifact_repo = ArtifactRepository(db)

    async def auto_deploy(self, todo_id: uuid.UUID) -> None:
        """原型产出后自动部署。

        工程模式：检测 prototype artifact 是否为 SPA 工程 → 触发 DeployService 上传 dist/
        """
        try:
            from arc.infrastructure.repositories.todo import TodoRepository

            todo = await TodoRepository(self._db).get_by_id(todo_id)
            if not todo or not todo.project_id:
                return

            artifacts = await self._artifact_repo.list_by_todo_id(todo_id)
            proto_art = next(
                (a for a in artifacts if a.artifact_type == ArtifactType.PROTOTYPE),
                None,
            )
            if not proto_art:
                return

            content = proto_art.content or {}

            if content.get("project_dir") and content.get("build_status") == "success":
                await self._maybe_inject_supabase_env(todo, proto_art)
                await self._deploy_project(todo, proto_art)
            else:
                logger.debug(
                    "Prototype artifact for todo %s is not in engineering mode, skipping deploy",
                    todo_id,
                )
        except Exception as exc:
            logger.debug("Auto-persist prototype failed: %s", exc)

    async def _maybe_inject_supabase_env(self, todo, artifact) -> None:
        """v5.6.0: 前端工程部署前注入 Supabase 连接信息到 .env。

        条件: APP_CODE.backend_type == "supabase" 且项目已 provision BaaS。
        写入 VITE_SUPABASE_URL/ANON_KEY/SCHEMA, 让生成的前端能连到自己的 schema。
        失败仅 warning 不阻断部署。
        """
        try:
            from arc.infrastructure.repositories.project import ProjectRepository

            content = artifact.content or {}
            if content.get("backend_type") != "supabase":
                return

            project = await ProjectRepository(self._db).get_by_id(todo.project_id)
            if not project or not project.local_path:
                return

            from arc.infrastructure.repositories.baas import BaasRepository

            baas_repo = BaasRepository(self._db)
            instance = await baas_repo.get_by_project(todo.project_id)
            if not instance:
                return

            project_dir = content.get("project_dir", "prototype")
            app_dir = (
                Path(project.local_path).expanduser().resolve() / project_dir
            )
            if not app_dir.is_dir():
                logger.debug("Skip Supabase env injection: app dir not found %s", app_dir)
                return

            from arc.config import settings

            env_content = (
                f"# 由 Arc v5.6.0 自动生成 — 对应项目 Supabase schema\n"
                f"VITE_SUPABASE_URL={settings.supabase_api_url}\n"
                f"VITE_SUPABASE_ANON_KEY={settings.supabase_anon_key}\n"
                f"VITE_SUPABASE_SCHEMA={instance.schema_name}\n"
            )
            env_file = app_dir / ".env"
            env_file.write_text(env_content, encoding="utf-8")
            logger.info(
                "Injected Supabase env for todo %s → schema %s",
                todo.id, instance.schema_name,
            )
        except Exception:
            logger.warning(
                "Supabase env injection failed for todo %s", todo.id, exc_info=True
            )

    async def _deploy_project(self, todo, artifact) -> None:
        """将原型工程的 build 产物部署到 S3，或本地 serve。"""
        from arc.infrastructure.repositories.project import (
            ProjectRepository,
            VersionRepository,
        )

        try:
            project = await ProjectRepository(self._db).get_by_id(todo.project_id)
            if not project or not project.local_path:
                logger.debug("Cannot deploy prototype: project has no local_path")
                return

            content = artifact.content or {}
            project_dir = content.get("project_dir", "prototype")
            artifact_path = content.get("artifact_path", "dist")
            local_dir = str(
                Path(project.local_path).expanduser().resolve()
                / project_dir
                / artifact_path
            )

            if not Path(local_dir).is_dir():
                logger.warning("Prototype build output not found: %s", local_dir)
                return

            # 统一构建门禁 (与 pipeline hooks.trigger_deployment 同口径，防空 build)
            from arc.application.execution.build_gate import check_build_ready

            build_result = check_build_ready(
                build_status=content.get("build_status", "success"),
                dist_dir=Path(local_dir),
            )
            if not build_result.ok:
                logger.warning("Prototype build gate failed: %s", build_result.reason)
                return

            if not todo.version_id:
                logger.debug("Cannot deploy prototype: todo has no version_id")
                return

            from arc.config import settings

            if not settings.storage_endpoint:
                await self._setup_local_preview(todo, artifact, local_dir)
                return

            from arc.application.deployment.service import DeployService

            # 断点D 修复: 按项目真实 project_type 路由 (原硬编码 STATIC_SITE,
            # 致 BINARY_APP 原型被当静态站点部署)。DeployService 内部按 type 选 deployer:
            # BINARY_APP → BinaryArtifactDeployer (不要求 index.html)。
            project_type = project.project_type
            deploy_config = resolve_deploy_config(project_type, content, artifact_path)

            deploy_svc = DeployService(self._db)
            deployment = await deploy_svc.deploy(
                project_id=todo.project_id,
                version_id=todo.version_id,
                local_dir=local_dir,
                project_type=project_type,
                todo_id=todo.id,
                config=deploy_config,
            )

            if deployment.deploy_url:
                content["preview_url"] = deployment.deploy_url
                artifact.content = content
                await self._artifact_repo.update(artifact)

                version_repo = VersionRepository(self._db)
                version = await version_repo.get_by_id(todo.version_id)
                if version:
                    version.set_prototype_preview_url(deployment.deploy_url)
                    await version_repo.update(version)

                logger.info(
                    "Deployed prototype project: todo=%s → %s",
                    todo.id,
                    deployment.deploy_url,
                )
            else:
                logger.warning(
                    "Prototype deploy failed: %s",
                    deployment.error_message,
                )
        except Exception as exc:
            logger.warning(
                "Prototype project deploy failed for todo %s: %s",
                todo.id,
                exc,
                exc_info=True,
            )

    async def _setup_local_preview(
        self, todo, artifact, local_dir: str
    ) -> None:
        """S3 未配置时，用 symlink 将构建产物暴露到 static/previews 目录。"""
        try:
            static_base = (
                Path(__file__).resolve().parent.parent.parent.parent
                / "static"
                / "previews"
            )
            static_base.mkdir(parents=True, exist_ok=True)

            link_name = static_base / str(todo.id)
            target = Path(local_dir)

            if link_name.is_symlink() or link_name.exists():
                link_name.unlink()
            link_name.symlink_to(target)

            preview_url = f"/static/previews/{todo.id}/index.html"

            content = artifact.content or {}
            content["preview_url"] = preview_url
            artifact.content = content
            await self._artifact_repo.update(artifact)

            logger.info(
                "Local prototype preview set up: todo=%s → %s",
                todo.id,
                preview_url,
            )
        except Exception as exc:
            logger.warning("Local preview setup failed: %s", exc)
