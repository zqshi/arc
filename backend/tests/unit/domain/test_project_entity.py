from __future__ import annotations

import uuid

import pytest

from arc.domain.errors import DomainError
from arc.domain.project.entity import Project, Version
from arc.domain.project.value_objects import (
    DEFAULT_CONVERSATION_CONFIG,
    DEFAULT_PIPELINE_CONFIG,
    ExecutionMode,
    ProjectStatus,
    VersionStatus,
)


class TestProjectCreation:
    def test_defaults(self) -> None:
        p = Project(name="My Project")
        assert p.name == "My Project"
        assert p.status == ProjectStatus.ACTIVE
        assert p.execution_mode == ExecutionMode.PIPELINE
        assert p.description == ""
        assert p.pipeline_config == DEFAULT_PIPELINE_CONFIG
        assert p.conversation_config == DEFAULT_CONVERSATION_CONFIG
        assert p.domain_model == {}
        assert p.github_token == ""
        assert p.github_config == {}

    def test_full_fields(self) -> None:
        oid = uuid.uuid4()
        p = Project(
            name="Full",
            organization_id=oid,
            description="desc",
            tech_stack="python",
            repo_url="https://github.com/test",
        )
        assert p.organization_id == oid
        assert p.tech_stack == "python"


class TestProjectBehavior:
    def _make(self) -> Project:
        return Project(name="Test")

    def test_archive(self) -> None:
        p = self._make()
        p.archive()
        assert p.status == ProjectStatus.ARCHIVED

    def test_activate(self) -> None:
        p = self._make()
        p.archive()
        p.activate()
        assert p.status == ProjectStatus.ACTIVE

    def test_set_execution_mode(self) -> None:
        p = self._make()
        p.set_execution_mode(ExecutionMode.CONVERSATION)
        assert p.execution_mode == ExecutionMode.CONVERSATION

    def test_update_pipeline_config_merges_defaults(self) -> None:
        p = self._make()
        p.update_pipeline_config({"auto_advance": True})
        assert p.pipeline_config["auto_advance"] is True
        assert "enabled_phases" in p.pipeline_config

    def test_update_conversation_config_merges_defaults(self) -> None:
        p = self._make()
        p.update_conversation_config({"auto_archive": False})
        assert p.conversation_config["auto_archive"] is False
        assert "required_deliverables" in p.conversation_config

    def test_update_pipeline_config_preserves_existing_custom(self) -> None:
        """部分更新不丢已有非默认值 (回归: 重置式 merge 会丢 phase_capabilities 等自定义)。"""
        p = self._make()
        p.update_pipeline_config({"gate_strictness": "moderate"})
        p.update_pipeline_config({"auto_advance": True})
        assert p.pipeline_config["gate_strictness"] == "moderate"
        assert p.pipeline_config["auto_advance"] is True

    def test_update_pipeline_config_deep_merges_phase_capabilities(self) -> None:
        """phase_capabilities 作为 dict 字段深度 merge, 不整体替换。"""
        p = self._make()
        p.update_phase_capabilities("development", ["cap-1"])
        p.update_pipeline_config({"phase_capabilities": {"testing": ["cap-2"]}})
        assert p.pipeline_config["phase_capabilities"]["development"] == ["cap-1"]
        assert p.pipeline_config["phase_capabilities"]["testing"] == ["cap-2"]

    def test_default_pipeline_config_has_phase_capabilities(self) -> None:
        p = self._make()
        assert p.pipeline_config["phase_capabilities"] == {}

    def test_update_phase_capabilities_sets_phase(self) -> None:
        p = self._make()
        p.update_phase_capabilities("development", ["cap-1", "cap-2"])
        assert p.pipeline_config["phase_capabilities"]["development"] == ["cap-1", "cap-2"]

    def test_update_phase_capabilities_invalid_phase_raises(self) -> None:
        p = self._make()
        with pytest.raises(DomainError):
            p.update_phase_capabilities("not_a_phase", ["cap-1"])

    def test_update_phase_capabilities_invalid_ids_raises(self) -> None:
        p = self._make()
        with pytest.raises(DomainError):
            p.update_phase_capabilities("development", "cap-1")

    def test_configure_github(self) -> None:
        p = self._make()
        p.configure_github("tok_123", "owner", "repo", "secret_abc")
        assert p.github_token == "tok_123"
        assert p.github_webhook_secret == "secret_abc"
        assert p.github_config == {"owner": "owner", "repo": "repo"}

    def test_disconnect_github(self) -> None:
        p = self._make()
        p.configure_github("tok", "o", "r", "s")
        p.disconnect_github()
        assert p.github_token == ""
        assert p.github_webhook_secret == ""
        assert p.github_config == {}


class TestVersionCreation:
    def test_defaults(self) -> None:
        v = Version(project_id=uuid.uuid4(), name="v1.0")
        assert v.name == "v1.0"
        assert v.status == VersionStatus.PLANNING
        assert v.goal == ""
        assert v.changelog == ""
        assert v.parent_version_id is None
        assert v.order == 0


class TestVersionTransitions:
    def _make(self) -> Version:
        return Version(project_id=uuid.uuid4(), name="v1.0")

    def test_activate(self) -> None:
        v = self._make()
        v.activate()
        assert v.status == VersionStatus.ACTIVE

    def test_release(self) -> None:
        v = self._make()
        v.activate()
        v.release()
        assert v.status == VersionStatus.RELEASED

    def test_replan_from_active(self) -> None:
        v = self._make()
        v.activate()
        v.replan()
        assert v.status == VersionStatus.PLANNING

    def test_invalid_release_from_planning(self) -> None:
        v = self._make()
        with pytest.raises(ValueError, match="Cannot transition"):
            v.release()

    def test_invalid_transition_from_released(self) -> None:
        v = self._make()
        v.activate()
        v.release()
        with pytest.raises(ValueError, match="Cannot transition"):
            v.activate()

    def test_set_changelog(self) -> None:
        v = self._make()
        before = v.updated_at
        v.set_changelog("initial release")
        assert v.changelog == "initial release"
        assert v.updated_at >= before


class TestVersionSetPrototypePreviewUrl:
    def _make(self) -> Version:
        return Version(project_id=uuid.uuid4(), name="v1.0")

    def test_set_url_success(self) -> None:
        v = self._make()
        before = v.updated_at
        v.set_prototype_preview_url("https://s3.example.com/previews/index.html")
        assert v.prototype_preview_url == "https://s3.example.com/previews/index.html"
        assert v.updated_at >= before

    def test_set_url_empty_string(self) -> None:
        v = self._make()
        v.set_prototype_preview_url("https://example.com/old")
        v.set_prototype_preview_url("")
        assert v.prototype_preview_url == ""

    def test_set_url_overwrites_previous(self) -> None:
        v = self._make()
        v.set_prototype_preview_url("https://old.com/preview")
        v.set_prototype_preview_url("https://new.com/preview")
        assert v.prototype_preview_url == "https://new.com/preview"

    def test_default_url_is_empty(self) -> None:
        v = self._make()
        assert v.prototype_preview_url == ""

    def test_updated_at_changes(self) -> None:
        import time
        v = self._make()
        first_update = v.updated_at
        time.sleep(0.01)
        v.set_prototype_preview_url("https://example.com/preview")
        assert v.updated_at >= first_update
