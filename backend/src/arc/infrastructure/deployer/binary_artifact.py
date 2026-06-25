"""二进制制品部署器 — 把原生客户端构建产物落制品目录。

与 StaticSiteDeployer 的差异:
- 不要求 index.html: 二进制产物(ELF/apk/exe 等)无统一入口, 验证目录非空即可
- prefix 用 artifacts/ (制品存储, 不分发; 分发在 v6.2 做下载页)
- url 为制品根路径, 不指向特定文件 (制品由用户/分发层选取)

不含构建逻辑 — 构建由 Agent 在容器沙箱内完成 (DockerSandboxRuntime)。
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


class BinaryArtifactDeployer(Deployer):
    """将二进制构建产物目录上传到制品存储 (不分发)。

    路径规范: artifacts/{project_id}/{deploy_id}/
    """

    def __init__(
        self,
        *,
        path_prefix: str = "artifacts",
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
        """执行部署: 上传 local_dir 下所有产物到制品存储。

        Args:
            local_dir: 构建产物目录 (如 src-tauri/target/release/bundle)
            project_id: 项目 ID
            deploy_id: 部署记录 ID

        Returns:
            DeployResult — success=True 时 url 为制品根公开地址
        """
        dist_path = Path(local_dir)
        if not dist_path.is_dir():
            return DeployResult(
                success=False,
                error=f"构建产物目录不存在: {local_dir}",
            )

        # 二进制制品无统一入口, 仅校验目录非空 (区别于静态站点的 index.html)
        if not any(dist_path.iterdir()):
            return DeployResult(
                success=False,
                error=f"无构建产物 (目录为空): {local_dir}",
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
            logger.error("Binary artifact upload failed: %s", e)
            return DeployResult(success=False, error=f"上传失败: {e}")

        # 制品根路径 (不指向 index.html; 具体制品由分发层/用户选取)
        url = get_public_url(prefix)

        logger.info(
            "Binary artifact deploy success: project=%s deploy=%s files=%d url=%s",
            project_id, deploy_id, file_count, url,
        )

        return DeployResult(
            success=True,
            url=url,
            prefix=prefix,
            file_count=file_count,
        )
