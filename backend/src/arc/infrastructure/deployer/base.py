"""部署器抽象基类。

所有部署器继承 ``Deployer``，实现 ``deploy()``。
新增部署器时在 ``infrastructure.deployer.get_deployer()`` 工厂注册映射。

设计：部署器只负责"把构建产物放到目标并返回访问信息"，不含构建逻辑
(构建由 Agent 在沙箱内完成)。不同 ProjectType 对应不同部署器实现。
"""
from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass


@dataclass
class DeployResult:
    """部署结果。"""

    success: bool
    url: str = ""
    prefix: str = ""
    file_count: int = 0
    error: str = ""


class Deployer(abc.ABC):
    """部署器抽象基类 — 将构建产物部署到目标，返回公开访问信息。

    每种 ProjectType (静态站点 / 二进制制品 / 容器镜像 ...) 对应一个
    ``Deployer`` 实现。新增类型时:
    1. 在此模块下新建 ``XxxDeployer(Deployer)``
    2. 在 ``get_deployer()`` 工厂注册 DeployType → Deployer 映射
    """

    @abc.abstractmethod
    async def deploy(
        self,
        *,
        local_dir: str,
        project_id: uuid.UUID,
        deploy_id: uuid.UUID,
    ) -> DeployResult:
        """执行部署。

        Args:
            local_dir: 构建产物目录（如 /workspace/dist）
            project_id: 项目 ID
            deploy_id: 部署记录 ID

        Returns:
            DeployResult — success=True 时 url 为公开访问地址
        """
        raise NotImplementedError
