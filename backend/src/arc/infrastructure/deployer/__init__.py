"""部署后端注册 + 工厂。"""
from __future__ import annotations

from arc.domain.deployment.value_objects import DeployType
from arc.infrastructure.deployer.base import DeployResult, Deployer
from arc.infrastructure.deployer.binary_artifact import BinaryArtifactDeployer
from arc.infrastructure.deployer.static_site import StaticSiteDeployer

__all__ = [
    "DeployResult",
    "Deployer",
    "StaticSiteDeployer",
    "BinaryArtifactDeployer",
    "get_deployer",
]


def get_deployer(
    deploy_type: DeployType,
    *,
    path_prefix: str | None = None,
) -> Deployer:
    """按部署类型返回部署器（工厂）。

    新增 ProjectType/DeployType 时在此注册映射。
    """
    if deploy_type == DeployType.STATIC_SITE:
        if path_prefix is not None:
            return StaticSiteDeployer(path_prefix=path_prefix)
        return StaticSiteDeployer()
    if deploy_type == DeployType.BINARY_ARTIFACT:
        if path_prefix is not None:
            return BinaryArtifactDeployer(path_prefix=path_prefix)
        return BinaryArtifactDeployer()
    raise ValueError(f"暂不支持的部署类型: {deploy_type}")
