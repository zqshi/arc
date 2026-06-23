"""Tests for domain/artifact field editability policy (v5.5.0)."""

from arc.domain.artifact.policy import (
    EDITABLE_FIELDS,
    filter_editable_fields,
    is_field_editable,
)
from arc.domain.artifact.value_objects import ArtifactType


class TestEditableFieldsCoverage:
    """EDITABLE_FIELDS 必须覆盖所有非 legacy artifact_type，避免漏配。"""

    def test_all_non_legacy_types_have_policy(self):
        non_legacy = {a for a in ArtifactType if a != ArtifactType.UI_DESIGN}
        assert non_legacy.issubset(set(EDITABLE_FIELDS.keys()))


class TestIsFieldEditable:
    def test_all_marker_type_accepts_any_field(self):
        assert is_field_editable(ArtifactType.DEV_REPORT, "implementation")
        assert is_field_editable(ArtifactType.DEV_REPORT, "arbitrary_new_field")
        assert is_field_editable(ArtifactType.REQUIREMENT_SPEC, "background")

    def test_empty_policy_rejects_everything(self):
        """工程产物（Agent 写入）所有字段都不可由用户编辑。"""
        assert not is_field_editable(ArtifactType.APP_CODE, "project_dir")
        assert not is_field_editable(ArtifactType.APP_CODE, "tech_stack")
        assert not is_field_editable(ArtifactType.PROTOTYPE, "routes")
        assert not is_field_editable(ArtifactType.PROTOTYPE, "build_status")

    def test_specific_field_whitelist(self):
        """SERVICE_SPEC 只允许 notes, 其他结构字段拒绝。"""
        assert is_field_editable(ArtifactType.SERVICE_SPEC, "notes")
        assert not is_field_editable(ArtifactType.SERVICE_SPEC, "endpoints")
        assert not is_field_editable(ArtifactType.SERVICE_SPEC, "data_persistence")

    def test_unknown_field_on_all_marker_still_editable(self):
        assert is_field_editable(ArtifactType.TEST_REPORT, "any_new_field")


class TestFilterEditableFields:
    def test_all_marker_returns_all_accepted(self):
        accepted, rejected = filter_editable_fields(
            ArtifactType.DEV_REPORT, ["implementation", "test_design"]
        )
        assert sorted(accepted) == ["implementation", "test_design"]
        assert rejected == []

    def test_empty_policy_rejects_all(self):
        accepted, rejected = filter_editable_fields(
            ArtifactType.APP_CODE, ["project_dir", "tech_stack"]
        )
        assert accepted == []
        assert sorted(rejected) == ["project_dir", "tech_stack"]

    def test_partial_whitelist_splits_correctly(self):
        accepted, rejected = filter_editable_fields(
            ArtifactType.SERVICE_SPEC, ["notes", "endpoints", "auth_strategy"]
        )
        assert accepted == ["notes"]
        assert sorted(rejected) == ["auth_strategy", "endpoints"]

    def test_empty_input_returns_empty(self):
        accepted, rejected = filter_editable_fields(ArtifactType.DEV_REPORT, [])
        assert accepted == []
        assert rejected == []

    def test_preserves_input_order_for_accepted(self):
        """可编辑字段保持用户提交顺序，便于 UI 回显。"""
        accepted, _ = filter_editable_fields(
            ArtifactType.DEV_REPORT, ["z_field", "a_field", "m_field"]
        )
        assert accepted == ["z_field", "a_field", "m_field"]
