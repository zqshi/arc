"""Tests for domain/sandbox/build_images — 构建镜像推导注册表。

镜像选择是 (project_type, build_target) 二维决策, 与 sandbox 配置解耦。
resolve_build_image 是纯函数, 不依赖 config 模块 (覆盖值作 dict 参数传入)。
"""

from arc.domain.project.value_objects import ProjectType
from arc.domain.sandbox.build_images import (
    DEFAULT_BUILD_IMAGES,
    default_sandbox_config,
    resolve_build_image,
)
from arc.domain.sandbox.value_objects import BuildTarget


class TestResolveBuildImage:
    def test_binary_app_tauri_linux_default(self):
        """BINARY_APP + TAURI_LINUX → arc/tauri-builder:linux (波次1 主线)。"""
        img = resolve_build_image(ProjectType.BINARY_APP, BuildTarget.TAURI_LINUX)
        assert img == "arc/tauri-builder:linux"

    def test_binary_app_web_default(self):
        """BINARY_APP + WEB → arc/web-builder:latest (v6.12 波次2)。"""
        img = resolve_build_image(ProjectType.BINARY_APP, BuildTarget.WEB)
        assert img == "arc/web-builder:latest"

    def test_overrides_takes_precedence(self):
        """config 覆盖值优先于默认注册表。"""
        overrides = {"binary_app:tauri_linux": "registry.example.com/tauri:v2"}
        img = resolve_build_image(
            ProjectType.BINARY_APP,
            BuildTarget.TAURI_LINUX,
            overrides=overrides,
        )
        assert img == "registry.example.com/tauri:v2"

    def test_unknown_combination_returns_empty(self):
        """未注册组合 (如 STATIC_SITE + TAURI_LINUX) 返回空串, 由调用方 fallback。"""
        img = resolve_build_image(ProjectType.STATIC_SITE, BuildTarget.TAURI_LINUX)
        assert img == ""

    def test_unknown_with_override_returns_override(self):
        """即使默认注册表无, overrides 仍生效 (允许外部完全接管镜像)。"""
        overrides = {"static_site:tauri_linux": "custom/img:latest"}
        img = resolve_build_image(
            ProjectType.STATIC_SITE,
            BuildTarget.TAURI_LINUX,
            overrides=overrides,
        )
        assert img == "custom/img:latest"


class TestDefaultBuildImages:
    def test_registry_contains_tauri_linux(self):
        """波次1 注册表至少含 BINARY_APP/TAURI_LINUX 主线。"""
        key = (ProjectType.BINARY_APP, BuildTarget.TAURI_LINUX)
        assert key in DEFAULT_BUILD_IMAGES
        assert DEFAULT_BUILD_IMAGES[key] == "arc/tauri-builder:linux"

    def test_registry_contains_web(self):
        """v6.12 波次2 注册表含 BINARY_APP/WEB。"""
        key = (ProjectType.BINARY_APP, BuildTarget.WEB)
        assert key in DEFAULT_BUILD_IMAGES
        assert DEFAULT_BUILD_IMAGES[key] == "arc/web-builder:latest"

    def test_static_site_web_not_registered(self):
        """STATIC_SITE + WEB 不注册 — web target 绑 BINARY_APP (化解 v6.0 重复矛盾)。"""
        img = resolve_build_image(ProjectType.STATIC_SITE, BuildTarget.WEB)
        assert img == ""


class TestDefaultSandboxConfig:
    """未显式配置 sandbox 时, 按项目类型返回默认策略 (断点B 修复)。"""

    def test_binary_app_defaults_to_docker(self):
        """BINARY_APP 自动启用容器化构建, 无需用户手动配 sandbox。"""
        cfg = default_sandbox_config(ProjectType.BINARY_APP)
        assert cfg == {"mode": "docker", "target": "tauri_linux"}

    def test_static_site_no_default_sandbox(self):
        """STATIC_SITE 默认不走 sandbox (维持现状)。"""
        assert default_sandbox_config(ProjectType.STATIC_SITE) is None
