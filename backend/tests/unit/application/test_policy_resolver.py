"""Tests for application/sandbox/policy_resolver — sandbox 策略解析 (断点A/B)。"""

from arc.application.sandbox.policy_resolver import resolve_sandbox_policy
from arc.domain.project.entity import Project
from arc.domain.project.value_objects import ProjectType
from arc.domain.sandbox.value_objects import BuildTarget, SandboxMode


def _project(project_type, sandbox=None):
    """构造项目; sandbox=None 表示无 sandbox 配置 (走默认注入)。"""
    conv = {"sandbox": sandbox} if sandbox is not None else {}
    return Project(name="t", project_type=project_type, conversation_config=conv)


class TestResolveSandboxPolicy:
    def test_binary_app_unconfigured_defaults_to_docker(self):
        """BINARY_APP 无 sandbox 配置 → 自动 docker + tauri-builder 镜像 (断点A+B)。"""
        p = _project(ProjectType.BINARY_APP)
        policy = resolve_sandbox_policy(p)
        assert policy is not None
        assert policy.mode == SandboxMode.DOCKER
        assert policy.build_target == BuildTarget.TAURI_LINUX
        assert policy.docker_image == "arc/tauri-builder:linux"

    def test_binary_app_explicit_none_respected(self):
        """用户显式 mode=none → 尊重, 不强制 sandbox。"""
        p = _project(ProjectType.BINARY_APP, sandbox={"mode": "none"})
        assert resolve_sandbox_policy(p) is None

    def test_binary_app_explicit_image_preserved(self):
        """用户显式配 docker_image → 不被推导覆盖。"""
        p = _project(
            ProjectType.BINARY_APP,
            sandbox={"mode": "docker", "docker_image": "custom:1"},
        )
        policy = resolve_sandbox_policy(p)
        assert policy is not None
        assert policy.docker_image == "custom:1"

    def test_static_site_unconfigured_no_sandbox(self):
        """STATIC_SITE 无配置 → None (维持宿主直跑现状)。"""
        p = _project(ProjectType.STATIC_SITE)
        assert resolve_sandbox_policy(p) is None

    def test_binary_app_explicit_target_routed(self):
        """显式 target=tauri_linux 仍推导出 tauri-builder 镜像。"""
        p = _project(
            ProjectType.BINARY_APP,
            sandbox={"mode": "docker", "target": "tauri_linux"},
        )
        policy = resolve_sandbox_policy(p)
        assert policy.build_target == BuildTarget.TAURI_LINUX
        assert policy.docker_image == "arc/tauri-builder:linux"

    def test_binary_app_web_target_routed(self):
        """v6.12 波次2: 显式 target=web → 推导 web-builder 镜像 (BINARY_APP web 资源构建)。"""
        p = _project(
            ProjectType.BINARY_APP,
            sandbox={"mode": "docker", "target": "web"},
        )
        policy = resolve_sandbox_policy(p)
        assert policy.build_target == BuildTarget.WEB
        assert policy.docker_image == "arc/web-builder:latest"

    def test_binary_app_capacitor_apk_target_routed(self):
        """v6.12 波次3: 显式 target=capacitor_apk → 推导 android-builder 镜像。"""
        p = _project(
            ProjectType.BINARY_APP,
            sandbox={"mode": "docker", "target": "capacitor_apk"},
        )
        policy = resolve_sandbox_policy(p)
        assert policy.build_target == BuildTarget.CAPACITOR_APK
        assert policy.docker_image == "arc/android-builder:linux"
