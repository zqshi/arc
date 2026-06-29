"""domain/deployment 实体行为单元测试。

测试覆盖:
- 创建（默认值、全字段）
- 状态转换（合法路径 + 非法路径抛异常）
- 值对象枚举完整性
- 边界条件
"""
from __future__ import annotations

import uuid

import pytest

from arc.domain.deployment.entity import Deployment
from arc.domain.deployment.value_objects import (
    DeployConfig,
    DeploymentStatus,
    DeployType,
)
from arc.domain.errors import DomainError


class TestDeploymentCreation:
    def test_defaults(self) -> None:
        d = Deployment(
            project_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
        )
        assert d.status == DeploymentStatus.PENDING
        assert d.deploy_type == DeployType.STATIC_SITE
        assert d.deploy_url is None
        assert d.storage_prefix is None
        assert d.files_uploaded == 0
        assert d.error_message is None
        assert d.deployed_at is None
        assert d.id is not None

    def test_full_fields(self) -> None:
        pid = uuid.uuid4()
        vid = uuid.uuid4()
        tid = uuid.uuid4()
        d = Deployment(
            project_id=pid,
            version_id=vid,
            todo_id=tid,
            deploy_type=DeployType.STATIC_SITE,
            build_command="pnpm build",
            artifact_path="out",
        )
        assert d.project_id == pid
        assert d.version_id == vid
        assert d.todo_id == tid
        assert d.build_command == "pnpm build"
        assert d.artifact_path == "out"


class TestDeploymentStateMachine:
    """状态机转换测试 — 覆盖全部合法路径和非法路径。"""

    def _make(self) -> Deployment:
        return Deployment(
            project_id=uuid.uuid4(),
            version_id=uuid.uuid4(),
        )

    # --- 合法路径 ---

    def test_pending_to_building(self) -> None:
        d = self._make()
        d.start_build()
        assert d.status == DeploymentStatus.BUILDING

    def test_building_to_uploading(self) -> None:
        d = self._make()
        d.start_build()
        d.start_upload()
        assert d.status == DeploymentStatus.UPLOADING

    def test_uploading_to_deployed(self) -> None:
        d = self._make()
        d.start_build()
        d.start_upload()
        d.complete(
            url="https://cdn.example.com/deploy/123/index.html",
            prefix="deployments/proj/123",
            file_count=42,
        )
        assert d.status == DeploymentStatus.DEPLOYED
        assert d.deploy_url == "https://cdn.example.com/deploy/123/index.html"
        assert d.storage_prefix == "deployments/proj/123"
        assert d.files_uploaded == 42
        assert d.deployed_at is not None

    def test_building_to_failed(self) -> None:
        d = self._make()
        d.start_build()
        d.fail("npm run build exited with code 1")
        assert d.status == DeploymentStatus.FAILED
        assert d.error_message == "npm run build exited with code 1"

    def test_uploading_to_failed(self) -> None:
        d = self._make()
        d.start_build()
        d.start_upload()
        d.fail("S3 connection timeout")
        assert d.status == DeploymentStatus.FAILED

    def test_deployed_to_rolled_back(self) -> None:
        d = self._make()
        d.start_build()
        d.start_upload()
        d.complete(url="url", prefix="prefix", file_count=1)
        d.rollback()
        assert d.status == DeploymentStatus.ROLLED_BACK

    # --- 非法路径 ---

    def test_pending_cannot_upload(self) -> None:
        d = self._make()
        with pytest.raises(DomainError, match="当前状态"):
            d.start_upload()

    def test_pending_cannot_complete(self) -> None:
        d = self._make()
        with pytest.raises(DomainError, match="当前状态"):
            d.complete(url="url", prefix="p", file_count=1)

    def test_building_cannot_complete(self) -> None:
        d = self._make()
        d.start_build()
        with pytest.raises(DomainError, match="当前状态"):
            d.complete(url="url", prefix="p", file_count=1)

    def test_deployed_cannot_build_again(self) -> None:
        d = self._make()
        d.start_build()
        d.start_upload()
        d.complete(url="url", prefix="p", file_count=1)
        with pytest.raises(DomainError, match="当前状态"):
            d.start_build()

    def test_failed_cannot_upload(self) -> None:
        d = self._make()
        d.start_build()
        d.fail("error")
        with pytest.raises(DomainError, match="当前状态"):
            d.start_upload()

    def test_pending_cannot_rollback(self) -> None:
        d = self._make()
        with pytest.raises(DomainError, match="当前状态"):
            d.rollback()


class TestDeployConfig:
    def test_defaults(self) -> None:
        cfg = DeployConfig()
        assert cfg.build_command == "npm run build"
        assert cfg.artifact_path == "dist"
        assert cfg.cdn_domain is None

    def test_custom(self) -> None:
        cfg = DeployConfig(
            build_command="pnpm build",
            artifact_path="out",
            cdn_domain="cdn.example.com",
        )
        assert cfg.build_command == "pnpm build"
        assert cfg.cdn_domain == "cdn.example.com"


class TestDeployConfigForType:
    """for_type 按 (project_type, build_target) 参数化 — v6.0 波次1。"""

    def test_binary_app_default_target_is_tauri_linux(self) -> None:
        from arc.domain.deployment.value_objects import DeployConfig
        from arc.domain.project.value_objects import ProjectType

        cfg = DeployConfig.for_type(ProjectType.BINARY_APP)
        assert cfg.build_command == "cargo tauri build"
        assert cfg.artifact_path == "src-tauri/target/release/bundle"

    def test_binary_app_explicit_tauri_linux(self) -> None:
        from arc.domain.deployment.value_objects import DeployConfig
        from arc.domain.project.value_objects import ProjectType
        from arc.domain.sandbox.value_objects import BuildTarget

        cfg = DeployConfig.for_type(ProjectType.BINARY_APP, BuildTarget.TAURI_LINUX)
        assert cfg.build_command == "cargo tauri build"

    def test_binary_app_web_target(self) -> None:
        """v6.12 波次2: BINARY_APP + WEB → npm run build + dist (web 资源构建, 不打包原生客户端)。"""
        from arc.domain.deployment.value_objects import DeployConfig
        from arc.domain.project.value_objects import ProjectType
        from arc.domain.sandbox.value_objects import BuildTarget

        cfg = DeployConfig.for_type(ProjectType.BINARY_APP, BuildTarget.WEB)
        assert cfg.build_command == "npm run build"
        assert cfg.artifact_path == "dist"

    def test_binary_app_capacitor_apk_target(self) -> None:
        """v6.12 波次3: BINARY_APP + CAPACITOR_APK → capacitor 多步构建产 apk。"""
        from arc.domain.deployment.value_objects import DeployConfig
        from arc.domain.project.value_objects import ProjectType
        from arc.domain.sandbox.value_objects import BuildTarget

        cfg = DeployConfig.for_type(ProjectType.BINARY_APP, BuildTarget.CAPACITOR_APK)
        assert "npx cap build android" in cfg.build_command
        assert cfg.artifact_path == "android/app/build/outputs/apk/release"

    def test_binary_app_tauri_windows_target(self) -> None:
        """v6.19 波次1: BINARY_APP + TAURI_WINDOWS → CI 编排。

        build_command 不被宿主执行 (linux docker 产不出 Windows 产物) — 仅作 CI
        workflow 构建语义参考, 实际构建步骤在 build-client-artifacts.yml 内, Agent
        经 build 工具 → BuildOrchestrationService 异步编排 (T3-g 设计2)。
        artifact_path="ci-products" 对齐 orchestrate._download_and_extract 解压目录。
        """
        from arc.domain.deployment.value_objects import DeployConfig
        from arc.domain.project.value_objects import ProjectType
        from arc.domain.sandbox.value_objects import BuildTarget

        cfg = DeployConfig.for_type(ProjectType.BINARY_APP, BuildTarget.TAURI_WINDOWS)
        assert cfg.build_command == "cargo tauri build"
        assert cfg.artifact_path == "ci-products"

    def test_static_site_ignores_target(self) -> None:
        """STATIC_SITE 不受 build_target 影响 (正交维度)。"""
        from arc.domain.deployment.value_objects import DeployConfig
        from arc.domain.project.value_objects import ProjectType
        from arc.domain.sandbox.value_objects import BuildTarget

        cfg = DeployConfig.for_type(ProjectType.STATIC_SITE, BuildTarget.TAURI_LINUX)
        assert cfg.build_command == "npm run build"
        assert cfg.artifact_path == "dist"


class TestDeploymentStatusEnum:
    def test_all_values(self) -> None:
        expected = {"pending", "building", "uploading", "deployed", "failed", "rolled_back"}
        assert {s.value for s in DeploymentStatus} == expected

    def test_deploy_type_values(self) -> None:
        assert DeployType.STATIC_SITE.value == "static_site"
