"""DeployService — 部署编排。

编排逻辑:
1. 创建 Deployment 实体（pending）
2. 验证构建产物存在
3. 调用 StaticSiteDeployer 上传
4. 更新 Deployment 状态 + Version 的 deploy_url
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.deployment.entity import Deployment
from arc.domain.deployment.value_objects import DeployConfig, DeploymentStatus, DeployType
from arc.infrastructure.deployer.static_site import StaticSiteDeployer
from arc.infrastructure.repositories.deployment import DeploymentRepository
from arc.infrastructure.repositories.project import ProjectRepository, VersionRepository

logger = logging.getLogger(__name__)


class DeployService:
    """编排部署全流程: 创建记录 → 上传 → 更新状态。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._deploy_repo = DeploymentRepository(db)
        self._project_repo = ProjectRepository(db)
        self._version_repo = VersionRepository(db)

    async def deploy_static_site(
        self,
        *,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
        local_dir: str,
        todo_id: uuid.UUID | None = None,
        config: DeployConfig | None = None,
    ) -> Deployment:
        """执行静态站点部署。

        Args:
            project_id: 项目 ID
            version_id: 版本 ID
            local_dir: 构建产物目录（完整路径）
            todo_id: 触发部署的需求 ID（可选）
            config: 部署配置（可选）

        Returns:
            部署实体（状态为 deployed 或 failed）

        补偿事务：任何阶段异常都确保状态标记为 failed，不留脏状态。
        """
        cfg = config or DeployConfig()

        deployment = Deployment(
            project_id=project_id,
            version_id=version_id,
            todo_id=todo_id,
            deploy_type=DeployType.STATIC_SITE,
            build_command=cfg.build_command,
            artifact_path=cfg.artifact_path,
        )

        # 持久化 pending 状态
        deployment = await self._deploy_repo.create(deployment)

        try:
            # 开始构建（实际构建由 Agent 完成，这里标记状态）
            deployment.start_build()
            await self._deploy_repo.update(deployment)

            # 开始上传
            deployment.start_upload()
            await self._deploy_repo.update(deployment)

            # 执行上传
            deployer = StaticSiteDeployer(
                path_prefix=self._get_deploy_prefix(),
            )
            result = await deployer.deploy(
                local_dir=local_dir,
                project_id=project_id,
                deploy_id=deployment.id,
            )

            if result.success:
                deployment.complete(
                    url=result.url,
                    prefix=result.prefix,
                    file_count=result.file_count,
                )
                # 回写 Version deploy_url
                await self._update_version_deploy_url(version_id, result.url)
            else:
                deployment.fail(result.error)
        except Exception as exc:
            # 补偿：任何异常都将状态标记为 failed，防止脏状态
            logger.error(
                "DeployService: deploy failed with exception project=%s: %s",
                project_id, exc,
            )
            try:
                deployment.fail(f"部署异常中断: {exc}")
            except Exception:
                # 如果状态转换也失败（如从不合法的状态转），强制设置
                deployment.status = DeploymentStatus.FAILED
                deployment.error_message = f"部署异常中断: {exc}"

        await self._deploy_repo.update(deployment)
        await self._db.commit()

        logger.info(
            "DeployService: project=%s version=%s status=%s url=%s",
            project_id, version_id, deployment.status.value, deployment.deploy_url,
        )
        return deployment

    async def get_latest_deployment(self, version_id: uuid.UUID) -> Deployment | None:
        """获取版本最新一次部署记录。"""
        return await self._deploy_repo.get_latest_by_version(version_id)

    async def list_deployments(
        self, project_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> list[Deployment]:
        """列出项目的部署历史。"""
        return await self._deploy_repo.list_by_project(project_id, offset=offset, limit=limit)

    async def rollback_deployment(self, deployment_id: uuid.UUID) -> Deployment:
        """回滚指定部署（标记状态，不删除文件）。"""
        deployment = await self._deploy_repo.get_by_id(deployment_id)
        if not deployment:
            raise ValueError(f"部署记录不存在: {deployment_id}")
        deployment.rollback()
        await self._deploy_repo.update(deployment)
        await self._db.commit()
        return deployment

    async def _update_version_deploy_url(self, version_id: uuid.UUID, url: str) -> None:
        """将部署 URL 回写到 Version 实体。"""
        version = await self._version_repo.get_by_id(version_id)
        if version:
            version.deploy_url = url
            await self._version_repo.update(version)

    @staticmethod
    def _get_deploy_prefix() -> str:
        from arc.config import settings
        return getattr(settings, "deploy_path_prefix", "deployments")
