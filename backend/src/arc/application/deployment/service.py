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

from arc.domain.deployment.distributor import DistributorType
from arc.domain.deployment.entity import Deployment
from arc.domain.deployment.signer import SignerType
from arc.domain.deployment.value_objects import DeployConfig, DeploymentStatus, DeployType
from arc.domain.errors import AppError, NotFoundError
from arc.domain.project.value_objects import ProjectType
from arc.infrastructure.deployer import get_deployer
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

    async def deploy(
        self,
        *,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
        local_dir: str,
        project_type: ProjectType,
        todo_id: uuid.UUID | None = None,
        config: DeployConfig | None = None,
        project=None,
        build_target=None,
    ) -> Deployment:
        """按项目类型路由部署。

        补偿事务：任何阶段异常都确保状态标记为 failed，不留脏状态。
        签名 (v6.1.0): build 后 upload 前签名, graceful skip (凭证未配/签名器未实现不阻断)。
        """
        cfg = config or DeployConfig.for_type(project_type)
        deploy_type = self._deploy_type_for(project_type)

        deployment = Deployment(
            project_id=project_id,
            version_id=version_id,
            todo_id=todo_id,
            deploy_type=deploy_type,
            build_command=cfg.build_command,
            artifact_path=cfg.artifact_path,
        )
        deployment = await self._deploy_repo.create(deployment)

        try:
            await self._execute_deploy_steps(
                deployment, project, build_target, local_dir,
                project_id, version_id, deploy_type,
            )
        except Exception as exc:
            self._handle_deploy_failure(deployment, exc, project_id)

        await self._deploy_repo.update(deployment)
        await self._db.commit()
        logger.info(
            "DeployService: project=%s version=%s status=%s url=%s",
            project_id, version_id, deployment.status.value, deployment.deploy_url,
        )
        return deployment

    async def _execute_deploy_steps(
        self,
        deployment,
        project,
        build_target,
        local_dir: str,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
        deploy_type,
    ) -> None:
        """执行 构建 → 签名 → 上传 → 部署 → 分发 主链路。

        产物分发 (v6.2.0 T5) graceful 不阻断 (产物已在制品仓可手动下载)。
        """
        # 开始构建（实际构建由 Agent 完成，这里标记状态）
        deployment.start_build()
        await self._deploy_repo.update(deployment)

        # 签名 (v6.1.0): build 后 upload 前。graceful skip — 不阻断部署。
        # 路由按产物平台 (.app/.exe/.apk) 检测, 非按 build_target。
        sign_results: list = []
        if project is not None:
            sign_results = await self._sign_artifact(
                deployment, project, build_target, local_dir,
            )

        # 开始上传
        deployment.start_upload()
        await self._deploy_repo.update(deployment)

        # 执行上传（按部署类型选部署器）
        deployer = get_deployer(deploy_type, path_prefix=self._get_deploy_prefix())
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
            # 制品分发层 (v6.2.0 T5): BINARY_APP 产物 distributor 上传 + 下载页/元数据。
            # graceful 不阻断 (产物已在制品仓可手动下载)。
            if project is not None and deploy_type == DeployType.BINARY_ARTIFACT:
                await self._distribute(
                    deployment, project, version_id, local_dir, sign_results, result.prefix
                )
        else:
            deployment.fail(result.error)

    def _handle_deploy_failure(
        self, deployment, exc: Exception, project_id: uuid.UUID
    ) -> None:
        """补偿：任何异常都将状态标记为 failed，防止脏状态。"""
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

    async def _sign_artifact(self, deployment, project, build_target, local_dir: str) -> list:
        """签名构建产物 (v6.1.0) — build 后 upload 前, graceful skip 不阻断。

        按产物平台 (.app/.exe/.apk 后缀) 选签名器, 非按 build_target 硬编码
        (tauri linux 的 deb/AppImage 无标准签名, 不签)。签名器/凭证未配 → skip。
        签名失败记 deployment.error 但不抛异常 (产物以未签名状态继续上传)。

        返回 sign_results [(SignerType, artifact_path, SignResult)] 供分发层 (T5)
        匹配产物签名状态 + 传 distributor.upload 的 signed 参数。
        """
        from arc.infrastructure.signer import get_signer, load_credentials_for_project

        # 产物平台 → SignerType (按后缀检测, 非 build_target)
        targets = self._detect_sign_targets(local_dir)
        if not targets:
            logger.info("DeployService: 无可签名产物 (local_dir=%s), 跳过签名", local_dir)
            return []

        sign_results: list = []
        for signer_type, artifact_path in targets:
            signer = get_signer(signer_type)
            if signer is None:
                logger.info("DeployService: 签名器 %s 未实现, 跳过", signer_type.value)
                continue
            creds = load_credentials_for_project(project, signer_type)
            try:
                result = await signer.sign(artifact_path, creds)
                sign_results.append((signer_type, artifact_path, result))
                if result.skipped:
                    logger.info(
                        "DeployService: 签名跳过 (%s): %s",
                        signer_type.value, result.error,
                    )
                elif not result.signed:
                    logger.warning(
                        "DeployService: 签名失败 (%s): %s",
                        signer_type.value, result.error,
                    )
                    deployment.error_message = f"签名失败({signer_type.value}): {result.error}"
            except Exception as e:
                logger.warning("DeployService: 签名异常 (%s): %s", signer_type.value, e)
                deployment.error_message = f"签名异常({signer_type.value}): {e}"
        return sign_results

    @staticmethod
    def _detect_sign_targets(local_dir: str) -> list:
        """扫描产物目录, 按平台后缀返回 [(SignerType, artifact_path)]。

        .app (目录) → APPLE; .exe → WINDOWS; .apk → ANDROID。
        deb/AppImage/无后缀 → 不签 (Linux 产物无标准签名机制)。
        """
        from pathlib import Path

        from arc.domain.deployment.signer import SignerType

        base = Path(local_dir)
        if not base.is_dir():
            return []

        targets = []
        # .app 是目录 (macOS bundle)
        for app_dir in base.rglob("*.app"):
            if app_dir.is_dir():
                targets.append((SignerType.APPLE, str(app_dir)))
        # .exe / .apk 是文件
        for ext, signer_type in (
            (".exe", SignerType.WINDOWS),
            (".apk", SignerType.ANDROID),
        ):
            for f in base.rglob(f"*{ext}"):
                if f.is_file():
                    targets.append((signer_type, str(f)))
        return targets

    async def _distribute(
        self,
        deployment,
        project,
        version_id: uuid.UUID,
        local_dir: str,
        sign_results: list,
        storage_prefix: str,
    ) -> None:
        """制品分发层 (v6.2.0 T5) — distributor 上传 + 下载页/更新元数据生成。

        graceful 不阻断: 产物已由 deployer 落制品仓, 分发失败仅记日志, deployment
        状态保持 DEPLOYED (分发是部署后的增强, 非部署成功条件)。
        """
        from arc.application.deployment.distribution import DistributionService

        try:
            version = await self._version_repo.get_by_id(version_id)
            if version is None:
                logger.warning("DeployService: version %s 不存在, 跳过分发", version_id)
                return
            svc = DistributionService()
            manifest = await svc.finalize(
                deployment, version, project, local_dir, sign_results, storage_prefix
            )
            deployment.set_distribution_manifest(svc.generate_manifest_json(manifest))
            logger.info(
                "DeployService: 分发完成 download_page=%s channels=%d",
                manifest.download_page_url, len(manifest.distributions),
            )
        except Exception as e:
            logger.warning("DeployService: 分发异常 (不阻断): %s", e)

    async def deploy_static_site(
        self,
        *,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
        local_dir: str,
        todo_id: uuid.UUID | None = None,
        config: DeployConfig | None = None,
    ) -> Deployment:
        """静态站点部署 — 薄封装，兼容现有调用点。

        新代码请直接用 ``deploy(project_type=ProjectType.STATIC_SITE, ...)``。
        """
        return await self.deploy(
            project_id=project_id,
            version_id=version_id,
            local_dir=local_dir,
            project_type=ProjectType.STATIC_SITE,
            todo_id=todo_id,
            config=config,
        )

    @staticmethod
    def _deploy_type_for(project_type: ProjectType) -> DeployType:
        """项目类型 → 部署类型映射。新增类型时在此扩展。"""
        if project_type == ProjectType.STATIC_SITE:
            return DeployType.STATIC_SITE
        if project_type == ProjectType.BINARY_APP:
            return DeployType.BINARY_ARTIFACT
        raise AppError(f"暂不支持的项目类型: {project_type}")

    async def get_latest_deployment(self, version_id: uuid.UUID) -> Deployment | None:
        """获取版本最新一次部署记录。"""
        return await self._deploy_repo.get_latest_by_version(version_id)

    async def list_deployments(
        self, project_id: uuid.UUID, *, offset: int = 0, limit: int = 20
    ) -> list[Deployment]:
        """列出项目的部署历史。"""
        return await self._deploy_repo.list_by_project(project_id, offset=offset, limit=limit)

    # ------------------------------------------------------------------
    # Credentials configuration (T2) — 接通零调用方的 encrypt + Project.set_*_creds
    # ------------------------------------------------------------------

    async def configure_signing_creds(
        self,
        project_id: uuid.UUID,
        platform: SignerType,
        creds: dict,
        *,
        user_id: uuid.UUID,
    ) -> dict:
        """配置某平台签名凭证 → 加密存 Project。空 creds 不存 (保持原值, 非清除)。

        读取侧 (load_credentials_for_project) 经 get_signing_creds(decrypt) 解密。
        """
        project = await self._get_project(project_id, user_id)
        from arc.infrastructure.crypto import encrypt

        project.set_signing_creds(platform, creds, encrypt)
        if creds:
            await self._project_repo.update(project)
            await self._db.commit()
        return {"platform": platform.value, "configured": bool(creds)}

    async def configure_distribution_creds(
        self,
        project_id: uuid.UUID,
        channel: DistributorType,
        creds: dict,
        *,
        user_id: uuid.UUID,
    ) -> dict:
        """配置某渠道分发凭证 → 加密存 Project (独立于签名凭证字段)。空 creds 不存 (保持原值)。"""
        project = await self._get_project(project_id, user_id)
        from arc.infrastructure.crypto import encrypt

        project.set_distribution_creds(channel, creds, encrypt)
        if creds:
            await self._project_repo.update(project)
            await self._db.commit()
        return {"channel": channel.value, "configured": bool(creds)}

    async def list_credentials(
        self, project_id: uuid.UUID, *, user_id: uuid.UUID
    ) -> dict:
        """列出各平台/渠道凭证配置状态 (mask 明文, 只返回 configured bool)。"""
        project = await self._get_project(project_id, user_id)
        from arc.infrastructure.crypto import decrypt

        return {
            "signing": {
                p.value: project.get_signing_creds(p, decrypt) is not None
                for p in SignerType
            },
            "distribution": {
                c.value: project.get_distribution_creds(c, decrypt) is not None
                for c in DistributorType
            },
        }

    async def _get_project(self, project_id: uuid.UUID, user_id: uuid.UUID):
        """取项目 (带 user_id 作用域, 非成员/不存在 → NotFoundError)。

        route 层 require_project_role(ADMIN) 已做角色校验; 此处 user_id 作用域为
        双重保险, 确保只能操作自己有权项目。
        """
        project = await self._project_repo.get_by_id(project_id, user_id=user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found or access denied")
        return project

    async def rollback_deployment(self, deployment_id: uuid.UUID) -> Deployment:
        """回滚指定部署（标记状态，不删除文件）。"""
        deployment = await self._deploy_repo.get_by_id(deployment_id)
        if not deployment:
            raise NotFoundError(f"部署记录不存在: {deployment_id}")
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
