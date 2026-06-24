"""Tests for artifact_deployer.resolve_deploy_config — 断点D 修复复现。

验证 BINARY_APP 原型不再被当 STATIC_SITE 部署: 按 project_type 路由 deploy config,
BINARY_APP 用类型默认 (cargo tauri build + bundle), 不信 content 的 build_command。
"""

from arc.application.execution.artifact_deployer import resolve_deploy_config
from arc.domain.project.value_objects import ProjectType


class TestResolveDeployConfig:
    def test_binary_app_uses_type_default_ignoring_content(self):
        """BINARY_APP 忽略 content 的 npm run build, 用 cargo tauri build (断点D 核心)。"""
        cfg = resolve_deploy_config(
            ProjectType.BINARY_APP,
            {"build_command": "npm run build"},
            "dist",
        )
        assert cfg.build_command == "cargo tauri build"
        assert cfg.artifact_path == "src-tauri/target/release/bundle"

    def test_static_site_uses_content_build_command(self):
        """STATIC_SITE 沿用 content 的 build_command (兼容既有行为)。"""
        cfg = resolve_deploy_config(
            ProjectType.STATIC_SITE,
            {"build_command": "pnpm build"},
            "out",
        )
        assert cfg.build_command == "pnpm build"
        assert cfg.artifact_path == "out"

    def test_static_site_defaults_when_content_missing(self):
        """STATIC_SITE 无 content build_command 时 fallback npm run build。"""
        cfg = resolve_deploy_config(ProjectType.STATIC_SITE, {}, "dist")
        assert cfg.build_command == "npm run build"
        assert cfg.artifact_path == "dist"
