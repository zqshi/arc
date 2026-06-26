"""Tests for domain/capability value objects (v6.8.0 W1)."""

import uuid

import pytest

from arc.domain.capability.errors import CapabilityError
from arc.domain.capability.value_objects import (
    CAPABILITY_TYPE_LABELS,
    Capability,
    CapabilityScope,
    CapabilityStatus,
    CapabilityType,
)

CAP_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class TestCapabilityType:
    def test_values(self):
        assert CapabilityType.AGENT == "agent"
        assert CapabilityType.SKILL == "skill"
        assert CapabilityType.MCP == "mcp"

    def test_completeness(self):
        expected = {"agent", "skill", "mcp"}
        assert {t.value for t in CapabilityType} == expected

    def test_labels(self):
        assert CAPABILITY_TYPE_LABELS[CapabilityType.AGENT] == "Agent"
        assert len(CAPABILITY_TYPE_LABELS) == 3


class TestCapabilityStatus:
    def test_values(self):
        assert CapabilityStatus.ACTIVE == "active"
        assert CapabilityStatus.DISABLED == "disabled"

    def test_completeness(self):
        assert {s.value for s in CapabilityStatus} == {"active", "disabled"}


class TestCapabilityScope:
    def test_values(self):
        assert CapabilityScope.GLOBAL == "global"
        assert CapabilityScope.PROJECT == "project"

    def test_completeness(self):
        assert {s.value for s in CapabilityScope} == {"global", "project"}


class TestCapability:
    def test_minimal_creation(self):
        cap = Capability(id=CAP_ID, name="openhands", type=CapabilityType.AGENT)
        assert cap.name == "openhands"
        assert cap.type == CapabilityType.AGENT
        assert cap.config == {}  # 默认空配置
        assert cap.status == CapabilityStatus.ACTIVE  # 默认启用
        assert cap.scope == CapabilityScope.GLOBAL  # 默认全局

    def test_full_creation(self):
        cap = Capability(
            id=CAP_ID,
            name="ui-design-skill",
            type=CapabilityType.SKILL,
            config={"directory": "/skills/ui-design"},
            status=CapabilityStatus.DISABLED,
            scope=CapabilityScope.PROJECT,
        )
        assert cap.config["directory"] == "/skills/ui-design"
        assert cap.status == CapabilityStatus.DISABLED
        assert cap.scope == CapabilityScope.PROJECT

    def test_immutable(self):
        cap = Capability(id=CAP_ID, name="x", type=CapabilityType.AGENT)
        with pytest.raises(AttributeError):
            cap.name = "changed"

    def test_is_active(self):
        active = Capability(id=CAP_ID, name="a", type=CapabilityType.AGENT)
        disabled = Capability(
            id=CAP_ID, name="b", type=CapabilityType.AGENT, status=CapabilityStatus.DISABLED
        )
        assert active.is_active is True
        assert disabled.is_active is False

    def test_is_agent(self):
        cap = Capability(id=CAP_ID, name="codex", type=CapabilityType.AGENT)
        assert cap.is_agent is True
        assert cap.is_skill is False

    def test_is_skill(self):
        cap = Capability(id=CAP_ID, name="ui", type=CapabilityType.SKILL)
        assert cap.is_skill is True
        assert cap.is_agent is False

    def test_empty_name_raises(self):
        with pytest.raises(CapabilityError):
            Capability(id=CAP_ID, name="", type=CapabilityType.AGENT)

    def test_whitespace_name_raises(self):
        with pytest.raises(CapabilityError):
            Capability(id=CAP_ID, name="   ", type=CapabilityType.AGENT)

    def test_equality(self):
        cap1 = Capability(id=CAP_ID, name="a", type=CapabilityType.AGENT)
        cap2 = Capability(id=CAP_ID, name="a", type=CapabilityType.AGENT)
        assert cap1 == cap2


class TestErrors:
    def test_capability_error_is_domain_error(self):
        from arc.domain.errors import DomainError

        err = CapabilityError("能力 name 不能为空")
        assert isinstance(err, DomainError)
        assert err.detail == "能力 name 不能为空"
