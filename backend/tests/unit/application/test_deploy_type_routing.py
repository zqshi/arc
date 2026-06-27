"""部署类型路由注册点一致性测试 (v6.10 TD-2 精简)。

验证 ProjectType → DeployType → Deployer → DeployConfig → prototype_guide
注册点一致, 新增类型时扩展断言。纯逻辑, 不依赖 db。

v6.10 TD-2:
- StorageAdapter/StaticSiteDeployer 测试迁至 tests/unit/infrastructure/test_storage_adapter.py
- _deploy_type_for 重复测试删除 (test_deployment_service.py TestDeployTypeFor 已覆盖同三路径)
- 原 test_deploy_service.py 重命名 (原内容混合, 名实不符)
"""
from __future__ import annotations

import pytest


class TestDeployTypeRouting:
    """v5.9.0: 部署类型路由注册点一致性。

    验证三处注册点一致: ProjectType → DeployType → Deployer → DeployConfig。
    新增类型时在此扩展断言。纯逻辑, 不依赖 db。
    """

    def test_get_deployer_returns_static_site_deployer(self) -> None:
        from arc.domain.deployment.value_objects import DeployType
        from arc.infrastructure.deployer import Deployer, get_deployer
        from arc.infrastructure.deployer.static_site import StaticSiteDeployer

        deployer = get_deployer(DeployType.STATIC_SITE)
        assert isinstance(deployer, StaticSiteDeployer)
        assert isinstance(deployer, Deployer)

    def test_get_deployer_returns_binary_artifact_deployer(self) -> None:
        from arc.domain.deployment.value_objects import DeployType
        from arc.infrastructure.deployer import Deployer, get_deployer
        from arc.infrastructure.deployer.binary_artifact import (
            BinaryArtifactDeployer,
        )

        deployer = get_deployer(DeployType.BINARY_ARTIFACT)
        assert isinstance(deployer, BinaryArtifactDeployer)
        assert isinstance(deployer, Deployer)

    def test_get_deployer_unsupported_raises(self) -> None:
        from arc.infrastructure.deployer import get_deployer

        with pytest.raises(ValueError, match="暂不支持的部署类型"):
            get_deployer("library")  # type: ignore[arg-type]

    def test_deploy_config_for_static_site(self) -> None:
        from arc.domain.deployment.value_objects import DeployConfig
        from arc.domain.project.value_objects import ProjectType

        cfg = DeployConfig.for_type(ProjectType.STATIC_SITE)
        assert cfg.build_command == "npm run build"
        assert cfg.artifact_path == "dist"

    def test_deploy_config_for_binary_app(self) -> None:
        from arc.domain.deployment.value_objects import DeployConfig
        from arc.domain.project.value_objects import ProjectType

        cfg = DeployConfig.for_type(ProjectType.BINARY_APP)
        assert cfg.build_command == "cargo tauri build"
        assert cfg.artifact_path == "src-tauri/target/release/bundle"

    def test_get_prototype_guide_for_static_site(self) -> None:
        from arc.application.context.content.methodology import get_prototype_guide
        from arc.domain.project.value_objects import ProjectType

        guide = get_prototype_guide(ProjectType.STATIC_SITE)
        assert guide  # 非空
        assert "前端工程" in guide  # 原型工程化指导关键文案

    def test_get_prototype_guide_for_binary_app(self) -> None:
        from arc.application.context.content.methodology import get_prototype_guide
        from arc.domain.project.value_objects import ProjectType

        guide = get_prototype_guide(ProjectType.BINARY_APP)
        assert guide  # 非空
        assert "原生客户端" in guide or "tauri" in guide.lower()

    def test_get_prototype_guide_unregistered_returns_empty(self) -> None:
        from arc.application.context.content.methodology import get_prototype_guide

        # 未注册类型返回空串, 不抛异常
        assert get_prototype_guide("library") == ""  # type: ignore[arg-type]
