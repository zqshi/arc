"""Tests for domain/artifact value objects."""

from arc.domain.artifact.value_objects import (
    ARTIFACT_LABELS,
    DELIVERABLE_REQUIRED_FIELDS,
    PHASE_ARTIFACT_MAP,
    PHASE_PRIMARY_ARTIFACT,
    ArtifactType,
)
from arc.domain.pipeline.value_objects import PhaseType


class TestArtifactType:
    def test_enum_values(self):
        assert ArtifactType.REQUIREMENT_SPEC == "requirement_spec"
        assert ArtifactType.INTERACTION_DESIGN == "interaction_design"
        assert ArtifactType.UI_SPEC == "ui_spec"
        assert ArtifactType.PROTOTYPE == "prototype"
        assert ArtifactType.TECH_ARCHITECTURE == "tech_architecture"
        assert ArtifactType.DEV_REPORT == "dev_report"
        assert ArtifactType.TEST_REPORT == "test_report"
        assert ArtifactType.DEPLOY_REPORT == "deploy_report"
        assert ArtifactType.EXPERIENCE_CARD == "experience_card"
        assert ArtifactType.UI_DESIGN == "ui_design"
        assert ArtifactType.APP_CODE == "app_code"
        assert ArtifactType.SERVICE_SPEC == "service_spec"

    def test_enum_completeness(self):
        expected = {
            "requirement_spec",
            "interaction_design",
            "ui_spec",
            "prototype",
            "tech_architecture",
            "dev_report",
            "test_report",
            "deploy_report",
            "experience_card",
            "ui_design",
            "app_code",
            "service_spec",
        }
        assert {a.value for a in ArtifactType} == expected

    def test_equality_same_value(self):
        assert ArtifactType.DEV_REPORT == ArtifactType("dev_report")

    def test_equality_string_coercion(self):
        assert ArtifactType.PROTOTYPE == "prototype"

    def test_invalid_value_raises(self):
        try:
            ArtifactType("nonexistent")
            assert False, "Should raise ValueError"
        except ValueError:
            pass


class TestPhaseArtifactMap:
    def test_all_mapped_phases_valid(self):
        for phase in PHASE_ARTIFACT_MAP:
            assert phase in PhaseType.__members__.values()

    def test_all_mapped_artifacts_valid(self):
        for artifacts in PHASE_ARTIFACT_MAP.values():
            for artifact in (artifacts if isinstance(artifacts, list) else [artifacts]):
                assert artifact in ArtifactType.__members__.values()

    def test_clarification_maps_to_requirement_spec(self):
        mapped = PHASE_ARTIFACT_MAP[PhaseType.CLARIFICATION]
        targets = mapped if isinstance(mapped, list) else [mapped]
        assert ArtifactType.REQUIREMENT_SPEC in targets

    def test_ui_design_maps_to_interaction_design(self):
        mapped = PHASE_ARTIFACT_MAP[PhaseType.UI_DESIGN]
        targets = mapped if isinstance(mapped, list) else [mapped]
        assert ArtifactType.INTERACTION_DESIGN in targets

    def test_architecture_maps_to_tech_architecture(self):
        mapped = PHASE_ARTIFACT_MAP[PhaseType.ARCHITECTURE]
        targets = mapped if isinstance(mapped, list) else [mapped]
        assert ArtifactType.TECH_ARCHITECTURE in targets

    def test_architecture_also_maps_to_service_spec(self):
        """v5.5.0: ARCHITECTURE 同时产出 SERVICE_SPEC 作为 BaaS 接入锚点。"""
        mapped = PHASE_ARTIFACT_MAP[PhaseType.ARCHITECTURE]
        targets = mapped if isinstance(mapped, list) else [mapped]
        assert ArtifactType.SERVICE_SPEC in targets

    def test_development_maps_to_dev_report(self):
        mapped = PHASE_ARTIFACT_MAP[PhaseType.DEVELOPMENT]
        targets = mapped if isinstance(mapped, list) else [mapped]
        assert ArtifactType.DEV_REPORT in targets

    def test_development_also_maps_to_app_code(self):
        """v5.5.0: DEVELOPMENT 同时产出 APP_CODE 作为机器可解析的代码工程元数据。"""
        mapped = PHASE_ARTIFACT_MAP[PhaseType.DEVELOPMENT]
        targets = mapped if isinstance(mapped, list) else [mapped]
        assert ArtifactType.APP_CODE in targets

    def test_testing_maps_to_test_report(self):
        mapped = PHASE_ARTIFACT_MAP[PhaseType.TESTING]
        targets = mapped if isinstance(mapped, list) else [mapped]
        assert ArtifactType.TEST_REPORT in targets

    def test_deployment_maps_to_deploy_report(self):
        mapped = PHASE_ARTIFACT_MAP[PhaseType.DEPLOYMENT]
        targets = mapped if isinstance(mapped, list) else [mapped]
        assert ArtifactType.DEPLOY_REPORT in targets

    def test_extraction_maps_to_experience_card(self):
        mapped = PHASE_ARTIFACT_MAP[PhaseType.EXTRACTION]
        targets = mapped if isinstance(mapped, list) else [mapped]
        assert ArtifactType.EXPERIENCE_CARD in targets

    def test_map_covers_expected_phases(self):
        expected_phases = {
            PhaseType.CLARIFICATION,
            PhaseType.UI_DESIGN,
            PhaseType.ARCHITECTURE,
            PhaseType.DEVELOPMENT,
            PhaseType.TESTING,
            PhaseType.DEPLOYMENT,
            PhaseType.EXTRACTION,
        }
        assert set(PHASE_ARTIFACT_MAP.keys()) == expected_phases


class TestArtifactLabels:
    def test_all_artifact_types_have_labels(self):
        for artifact_type in ArtifactType:
            assert artifact_type in ARTIFACT_LABELS
            assert isinstance(ARTIFACT_LABELS[artifact_type], str)
            assert len(ARTIFACT_LABELS[artifact_type]) > 0

    def test_label_values(self):
        assert ARTIFACT_LABELS[ArtifactType.REQUIREMENT_SPEC] == "需求规格"
        assert ARTIFACT_LABELS[ArtifactType.INTERACTION_DESIGN] == "交互设计"
        assert ARTIFACT_LABELS[ArtifactType.UI_SPEC] == "视觉规范"
        assert ARTIFACT_LABELS[ArtifactType.PROTOTYPE] == "原型设计"
        assert ARTIFACT_LABELS[ArtifactType.TECH_ARCHITECTURE] == "技术架构"
        assert ARTIFACT_LABELS[ArtifactType.DEV_REPORT] == "开发报告"
        assert ARTIFACT_LABELS[ArtifactType.TEST_REPORT] == "测试报告"
        assert ARTIFACT_LABELS[ArtifactType.DEPLOY_REPORT] == "部署报告"
        assert ARTIFACT_LABELS[ArtifactType.EXPERIENCE_CARD] == "经验卡片"
        assert ARTIFACT_LABELS[ArtifactType.UI_DESIGN] == "UI设计(旧)"
        assert ARTIFACT_LABELS[ArtifactType.APP_CODE] == "应用代码"
        assert ARTIFACT_LABELS[ArtifactType.SERVICE_SPEC] == "服务契约"


class TestPhasePrimaryArtifact:
    """v5.5.0: APP_CODE/SERVICE_SPEC 是次要 artifact，不应抢占 primary 位。"""

    def test_development_primary_is_dev_report(self):
        assert PHASE_PRIMARY_ARTIFACT[PhaseType.DEVELOPMENT] == ArtifactType.DEV_REPORT

    def test_architecture_primary_is_tech_architecture(self):
        assert PHASE_PRIMARY_ARTIFACT[PhaseType.ARCHITECTURE] == ArtifactType.TECH_ARCHITECTURE


class TestDeliverableRequiredFields:
    """v5.5.0: 新增 APP_CODE / SERVICE_SPEC 必填字段定义。"""

    def test_all_artifact_types_have_required_fields(self):
        """每个非 legacy artifact_type 都应在 DELIVERABLE_REQUIRED_FIELDS 中有定义。"""
        non_legacy_types = {
            a.value for a in ArtifactType if a != ArtifactType.UI_DESIGN
        }
        assert non_legacy_types.issubset(set(DELIVERABLE_REQUIRED_FIELDS.keys()))

    def test_app_code_required_fields(self):
        required = DELIVERABLE_REQUIRED_FIELDS["app_code"]
        assert "project_dir" in required
        assert "tech_stack" in required
        assert "build_command" in required
        assert "run_command" in required
        assert "entry_points" in required

    def test_service_spec_required_fields(self):
        required = DELIVERABLE_REQUIRED_FIELDS["service_spec"]
        assert "data_model_ref" in required
        assert "data_persistence" in required
        assert "endpoints" in required
        assert "auth_strategy" in required
