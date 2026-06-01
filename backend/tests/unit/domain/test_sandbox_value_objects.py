"""Tests for domain/sandbox value objects."""

from arc.domain.sandbox.value_objects import SandboxMode, SandboxPolicy


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
