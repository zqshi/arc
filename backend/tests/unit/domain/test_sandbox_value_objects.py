"""Tests for domain/sandbox value objects."""

from arc.domain.sandbox.value_objects import (
    BuildTarget,
    SandboxMode,
    SandboxPolicy,
)


class TestSandboxPolicy:
    def test_default_policy(self):
        p = SandboxPolicy()
        assert p.mode == SandboxMode.NONE
        assert p.timeout_seconds == 120
        assert p.network_enabled is False

    def test_from_dict_none(self):
        p = SandboxPolicy.from_dict(None)
        assert p.mode == SandboxMode.NONE

    def test_from_dict_empty(self):
        p = SandboxPolicy.from_dict({})
        assert p.mode == SandboxMode.NONE

    def test_from_dict_docker(self):
        p = SandboxPolicy.from_dict({
            "mode": "docker",
            "docker_image": "node:20",
            "timeout_seconds": 60,
            "network_enabled": True,
        })
        assert p.mode == SandboxMode.DOCKER
        assert p.docker_image == "node:20"
        assert p.timeout_seconds == 60
        assert p.network_enabled is True

    def test_from_dict_approval_gate(self):
        p = SandboxPolicy.from_dict({
            "mode": "approval_gate",
            "approval_required_for": ["run_command"],
        })
        assert p.mode == SandboxMode.APPROVAL_GATE
        assert p.approval_required_for == ["run_command"]

    def test_from_dict_invalid_mode(self):
        p = SandboxPolicy.from_dict({"mode": "nonexistent"})
        assert p.mode == SandboxMode.NONE

    def test_frozen(self):
        p = SandboxPolicy()
        try:
            p.mode = SandboxMode.DOCKER  # type: ignore
            assert False, "Should raise"
        except Exception:
            pass  # frozen=True prevents mutation


class TestBuildTarget:
    def test_tauri_linux_value(self):
        assert BuildTarget.TAURI_LINUX == "tauri_linux"


class TestSandboxPolicyBuildTarget:
    """build_target 记录构建目标语义; 镜像解析在 application 层, 不在此。"""

    def test_default_build_target(self):
        p = SandboxPolicy()
        assert p.build_target == BuildTarget.TAURI_LINUX

    def test_from_dict_parses_target(self):
        p = SandboxPolicy.from_dict({
            "mode": "docker",
            "target": "tauri_linux",
        })
        assert p.mode == SandboxMode.DOCKER
        assert p.build_target == BuildTarget.TAURI_LINUX

    def test_from_dict_invalid_target_falls_back(self):
        """未知 target 值降级为默认 TAURI_LINUX (不阻断, 遵循降级原则)。"""
        p = SandboxPolicy.from_dict({"mode": "docker", "target": "nonexistent"})
        assert p.build_target == BuildTarget.TAURI_LINUX

    def test_from_dict_without_target_uses_default(self):
        p = SandboxPolicy.from_dict({"mode": "docker"})
        assert p.build_target == BuildTarget.TAURI_LINUX
