"""S3 静态站点部署后端。

职责: 将本地 dist 目录上传到 S3，返回公开访问 URL。
不含构建逻辑 — 构建由 Agent 在沙箱内完成。
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from arc.infrastructure.deployer.base import Deployer, DeployResult
from arc.infrastructure.storage import (
    DEPLOY_MAX_UPLOAD_SIZE,
    get_public_url,
    get_storage,
)

logger = logging.getLogger(__name__)


class StaticSiteDeployer(Deployer):
    """将构建产物目录上传到 S3 作为静态站点。

    路径规范: deployments/{project_id}/{deploy_id}/
    """

    def __init__(
        self,
        *,
        path_prefix: str = "deployments",
        max_file_size: int = DEPLOY_MAX_UPLOAD_SIZE,
    ):
        self._path_prefix = path_prefix
        self._max_file_size = max_file_size

    async def deploy(
        self,
        *,
        local_dir: str,
        project_id: uuid.UUID,
        deploy_id: uuid.UUID,
    ) -> DeployResult:
        """执行部署: 上传 local_dir 下所有文件到 S3。

        Args:
            local_dir: 构建产物目录（如 /workspace/dist）
            project_id: 项目 ID
            deploy_id: 部署记录 ID

        Returns:
            DeployResult — success=True 时 url 为 index.html 公开地址
        """
        dist_path = Path(local_dir)
        if not dist_path.is_dir():
            return DeployResult(
                success=False,
                error=f"构建产物目录不存在: {local_dir}",
            )

        # 检查 index.html 存在（静态站点入口）
        index_file = dist_path / "index.html"
        if not index_file.exists():
            return DeployResult(
                success=False,
                error=f"构建产物缺少 index.html: {local_dir}",
            )

        prefix = f"{self._path_prefix}/{project_id}/{deploy_id}"

        try:
            storage = get_storage()
            file_count = await storage.async_upload_dir(
                local_dir, prefix, max_file_size=self._max_file_size
            )
        except ValueError as e:
            return DeployResult(success=False, error=str(e))
        except Exception as e:
            logger.error("Deploy upload failed: %s", e)
            return DeployResult(success=False, error=f"上传失败: {e}")

        url = get_public_url(f"{prefix}/index.html")

        logger.info(
            "Static deploy success: project=%s deploy=%s files=%d url=%s",
            project_id, deploy_id, file_count, url,
        )

        return DeployResult(
            success=True,
            url=url,
            prefix=prefix,
            file_count=file_count,
        )
