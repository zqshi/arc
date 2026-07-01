"""Tests for domain/project value objects."""

import pytest

from arc.domain.project.value_objects import (
    DEFAULT_CONVERSATION_CONFIG,
    DEFAULT_PIPELINE_CONFIG,
    DELIVERABLES_BY_TYPE,
    PHASES_BY_TYPE,
    REQUIRED_DELIVERABLES,
    VALID_VERSION_TRANSITIONS,
    AgentAutonomy,
    GateStrictness,
    GitSyncConfig,
    LoopConfig,
    ProcessConfig,
    ProcessConstraint,
    ProjectStatus,
    ProjectType,
    VersionStatus,
    deliverables_for_type,
    is_deliverable_visible,
)


class TestProjectStatus:
    def test_enum_values_complete(self):
        expected = {"active", "archived", "deleted"}
        assert {ps.value for ps in ProjectStatus} == expected

    def test_enum_count(self):
        assert len(ProjectStatus) == 3

    def test_str_equality(self):
        assert ProjectStatus.ACTIVE == "active"
        assert ProjectStatus.ARCHIVED == "archived"
        assert ProjectStatus.DELETED == "deleted"

    def test_identity_equality(self):
        assert ProjectStatus.ACTIVE == ProjectStatus.ACTIVE

    def test_from_value(self):
        assert ProjectStatus("archived") == ProjectStatus.ARCHIVED


class TestGateStrictness:
    def test_enum_values_complete(self):
        expected = {"strict", "moderate", "relaxed"}
        assert {gs.value for gs in GateStrictness} == expected

    def test_enum_count(self):
        assert len(GateStrictness) == 3

    def test_str_equality(self):
        assert GateStrictness.STRICT == "strict"
        assert GateStrictness.MODERATE == "moderate"
        assert GateStrictness.RELAXED == "relaxed"

    def test_from_value(self):
        assert GateStrictness("relaxed") == GateStrictness.RELAXED


class TestAgentAutonomy:
    def test_enum_values_complete(self):
        expected = {"full", "supervised"}
        assert {aa.value for aa in AgentAutonomy} == expected

    def test_enum_count(self):
        assert len(AgentAutonomy) == 2

    def test_str_equality(self):
        assert AgentAutonomy.FULL == "full"
        assert AgentAutonomy.SUPERVISED == "supervised"

    def test_from_value(self):
        assert AgentAutonomy("supervised") == AgentAutonomy.SUPERVISED


class TestVersionStatus:
    def test_enum_values_complete(self):
        expected = {"planning", "active", "released"}
        assert {vs.value for vs in VersionStatus} == expected

    def test_enum_count(self):
        assert len(VersionStatus) == 3

    def test_str_equality(self):
        assert VersionStatus.PLANNING == "planning"
        assert VersionStatus.ACTIVE == "active"
        assert VersionStatus.RELEASED == "released"

    def test_from_value(self):
        assert VersionStatus("active") == VersionStatus.ACTIVE


class TestValidVersionTransitions:
    def test_all_statuses_have_transitions(self):
        for vs in VersionStatus:
            assert vs in VALID_VERSION_TRANSITIONS

    def test_planning_can_go_to_active(self):
        assert VALID_VERSION_TRANSITIONS[VersionStatus.PLANNING] == {
            VersionStatus.ACTIVE,
        }

    def test_active_can_go_to_released_or_planning(self):
        assert VALID_VERSION_TRANSITIONS[VersionStatus.ACTIVE] == {
            VersionStatus.RELEASED,
            VersionStatus.PLANNING,
        }

    def test_released_is_terminal(self):
        assert VALID_VERSION_TRANSITIONS[VersionStatus.RELEASED] == set()

    def test_no_transition_to_self(self):
        for status, targets in VALID_VERSION_TRANSITIONS.items():
            assert status not in targets

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            VersionStatus("nonexistent")


class TestDefaultPipelineConfig:
    def test_has_enabled_phases(self):
        assert "enabled_phases" in DEFAULT_PIPELINE_CONFIG
        assert len(DEFAULT_PIPELINE_CONFIG["enabled_phases"]) == 7

    def test_has_required_phases(self):
        assert "required_phases" in DEFAULT_PIPELINE_CONFIG
        assert len(DEFAULT_PIPELINE_CONFIG["required_phases"]) == len(DEFAULT_PIPELINE_CONFIG["enabled_phases"])

    def test_required_phases_subset_of_enabled(self):
        enabled = set(DEFAULT_PIPELINE_CONFIG["enabled_phases"])
        required = set(DEFAULT_PIPELINE_CONFIG["required_phases"])
        assert required.issubset(enabled)

    def test_gate_strictness_is_strict(self):
        assert DEFAULT_PIPELINE_CONFIG["gate_strictness"] == "strict"

    def test_auto_advance_disabled(self):
        assert DEFAULT_PIPELINE_CONFIG["auto_advance"] is False

    def test_enabled_phases_match_phase_type_values(self):
        from arc.domain.pipeline.value_objects import PhaseType

        expected = {pt.value for pt in PhaseType}
        actual = set(DEFAULT_PIPELINE_CONFIG["enabled_phases"])
        assert actual == expected


class TestDefaultConversationConfig:
    def test_has_required_deliverables(self):
        assert "required_deliverables" in DEFAULT_CONVERSATION_CONFIG
        from arc.domain.project.value_objects import REQUIRED_DELIVERABLES
        assert len(DEFAULT_CONVERSATION_CONFIG["required_deliverables"]) == len(REQUIRED_DELIVERABLES)

    def test_agent_autonomy_is_supervised(self):
        assert DEFAULT_CONVERSATION_CONFIG["agent_autonomy"] == "supervised"

    def test_auto_archive_enabled(self):
        assert DEFAULT_CONVERSATION_CONFIG["auto_archive"] is True

    def test_loop_config_present(self):
        loop = DEFAULT_CONVERSATION_CONFIG["loop_config"]
        assert "token_budget" in loop
        assert "wall_timeout_seconds" in loop
        assert "max_tokens_per_call" in loop

    def test_loop_config_values_positive(self):
        loop = DEFAULT_CONVERSATION_CONFIG["loop_config"]
        assert loop["token_budget"] > 0
        assert loop["wall_timeout_seconds"] > 0
        assert loop["max_tokens_per_call"] > 0

    def test_git_sync_present(self):
        git = DEFAULT_CONVERSATION_CONFIG["git_sync"]
        assert "auto_commit" in git
        assert "auto_push" in git
        assert "commit_prefix" in git
        assert "target_branch" in git

    def test_git_sync_defaults_conservative(self):
        git = DEFAULT_CONVERSATION_CONFIG["git_sync"]
        assert git["auto_commit"] is False
        assert git["auto_push"] is False


class TestGitSyncConfig:
    """v6.23 D2: git_sync 子结构值对象 — 防 session_manager 裸读拼写错误 + 默认值单一源。"""

    def test_from_dict_full(self):
        cfg = GitSyncConfig.from_dict({
            "auto_commit": True,
            "auto_push": True,
            "commit_prefix": "fix",
            "target_branch": "main",
        })
        assert cfg.auto_commit is True
        assert cfg.auto_push is True
        assert cfg.commit_prefix == "fix"
        assert cfg.target_branch == "main"

    def test_from_dict_partial_uses_defaults(self):
        cfg = GitSyncConfig.from_dict({"auto_commit": True})
        assert cfg.auto_commit is True
        assert cfg.auto_push is False  # 默认
        assert cfg.commit_prefix == "feat"  # 默认
        assert cfg.target_branch == ""  # 默认

    def test_from_dict_empty_returns_defaults(self):
        cfg = GitSyncConfig.from_dict({})
        assert cfg == GitSyncConfig()

    def test_from_dict_none_returns_defaults(self):
        cfg = GitSyncConfig.from_dict(None)
        assert cfg == GitSyncConfig()

    def test_from_dict_ignores_unknown_keys(self):
        """旧数据/多余键不应报错, 只取已知字段 (同 ProcessConfig.from_dict 范式)。"""
        cfg = GitSyncConfig.from_dict({"auto_commit": True, "legacy_key": "x"})
        assert cfg.auto_commit is True

    def test_defaults_match_default_conversation_config(self):
        """drift guard: VO 默认值必须与 DEFAULT_CONVERSATION_CONFIG['git_sync'] 一致。"""
        default_dict = DEFAULT_CONVERSATION_CONFIG["git_sync"]
        cfg = GitSyncConfig()
        assert cfg.auto_commit == default_dict["auto_commit"]
        assert cfg.auto_push == default_dict["auto_push"]
        assert cfg.commit_prefix == default_dict["commit_prefix"]
        assert cfg.target_branch == default_dict["target_branch"]

    def test_frozen_immutable(self):
        cfg = GitSyncConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.auto_commit = True  # type: ignore[misc]


class TestLoopConfig:
    """v6.23 D2: loop_config 子结构值对象 — 防 build_loop_config 裸读拼写错误 + 默认值单一源。

    LoopConfig 从 application/execution/agent_loop.py 迁入 domain:
    - 3 持久化字段 (token_budget/wall_timeout_seconds/max_tokens_per_call) 来自 conversation_config
    - max_validation_retries 为 AgentLoop 运行时默认, 不持久化 (from_conversation_config 不读)
    """

    def test_from_conversation_config_full(self):
        cfg = LoopConfig.from_conversation_config({
            "loop_config": {
                "token_budget": 50000,
                "wall_timeout_seconds": 120,
                "max_tokens_per_call": 8192,
            },
        })
        assert cfg.token_budget == 50000
        assert cfg.wall_timeout_seconds == 120
        assert cfg.max_tokens_per_call == 8192

    def test_from_conversation_config_partial_uses_defaults(self):
        cfg = LoopConfig.from_conversation_config({
            "loop_config": {"token_budget": 50000},
        })
        assert cfg.token_budget == 50000
        assert cfg.wall_timeout_seconds == 300.0  # 默认
        assert cfg.max_tokens_per_call == 16384  # 默认

    def test_from_conversation_config_empty_returns_defaults(self):
        cfg = LoopConfig.from_conversation_config({})
        assert cfg == LoopConfig()

    def test_from_conversation_config_none_returns_defaults(self):
        cfg = LoopConfig.from_conversation_config(None)
        assert cfg == LoopConfig()

    def test_from_conversation_config_missing_loop_config_key(self):
        """config 存在但无 loop_config 子键 → 全默认。"""
        cfg = LoopConfig.from_conversation_config({"auto_archive": False})
        assert cfg == LoopConfig()

    def test_from_conversation_config_ignores_unknown_keys(self):
        cfg = LoopConfig.from_conversation_config({
            "loop_config": {"token_budget": 50000, "legacy": "x"},
        })
        assert cfg.token_budget == 50000

    def test_max_validation_retries_not_read_from_dict(self):
        """max_validation_retries 是运行时默认, from_conversation_config 不从 dict 读
        (持久化层不存此键, 防误读脏数据)。"""
        cfg = LoopConfig.from_conversation_config({
            "loop_config": {"max_validation_retries": 99},
        })
        assert cfg.max_validation_retries == 2  # 保持默认, 不读 dict

    def test_defaults_match_default_conversation_config(self):
        """drift guard: 3 持久化字段默认值必须与 DEFAULT_CONVERSATION_CONFIG['loop_config'] 一致。"""
        default_dict = DEFAULT_CONVERSATION_CONFIG["loop_config"]
        cfg = LoopConfig()
        assert cfg.token_budget == default_dict["token_budget"]
        assert cfg.wall_timeout_seconds == default_dict["wall_timeout_seconds"]
        assert cfg.max_tokens_per_call == default_dict["max_tokens_per_call"]

    def test_frozen_immutable(self):
        cfg = LoopConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.token_budget = 1  # type: ignore[misc]


class TestProjectType:
    """项目交付/部署形态枚举。v5.9.0 static_site, v6.0.0 激活 binary_app。"""

    def test_enum_values_complete(self):
        assert {pt.value for pt in ProjectType} == {"static_site", "binary_app"}

    def test_enum_count(self):
        assert len(ProjectType) == 2

    def test_str_equality(self):
        assert ProjectType.STATIC_SITE == "static_site"

    def test_identity_equality(self):
        assert ProjectType.STATIC_SITE == ProjectType.STATIC_SITE

    def test_from_value(self):
        assert ProjectType("static_site") == ProjectType.STATIC_SITE
        assert ProjectType("binary_app") == ProjectType.BINARY_APP

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ProjectType("library")  # 未激活类型


class TestDeliverablesByType:
    """v6.9: 按项目类型裁剪可见交付物 — 非app类不应显示 app_code/构建产物。"""

    def test_all_types_covered(self):
        for pt in ProjectType:
            assert pt in DELIVERABLES_BY_TYPE

    def test_static_site_excludes_app_code(self):
        """静态站点无原生构建产物, app_code 不可见。"""
        visible = DELIVERABLES_BY_TYPE[ProjectType.STATIC_SITE]
        assert "app_code" not in visible

    def test_static_site_excludes_build(self):
        """静态站点无构建产物锚点, build 不可见。"""
        visible = DELIVERABLES_BY_TYPE[ProjectType.STATIC_SITE]
        assert "build" not in visible

    def test_binary_app_includes_app_code(self):
        visible = DELIVERABLES_BY_TYPE[ProjectType.BINARY_APP]
        assert "app_code" in visible

    def test_binary_app_includes_build(self):
        """原生客户端有构建产物, build 可见(签名/分发锚点)。"""
        visible = DELIVERABLES_BY_TYPE[ProjectType.BINARY_APP]
        assert "build" in visible

    def test_static_site_subset_of_required(self):
        """静态站点可见交付物是全量的子集(只裁剪, 不新增)。"""
        assert DELIVERABLES_BY_TYPE[ProjectType.STATIC_SITE].issubset(
            set(REQUIRED_DELIVERABLES)
        )

    def test_binary_app_superset_of_required(self):
        """原生客户端含全量 + 构建产物 build。"""
        assert set(REQUIRED_DELIVERABLES).issubset(
            DELIVERABLES_BY_TYPE[ProjectType.BINARY_APP]
        )

    def test_common_deliverables_visible_for_all(self):
        """基础交付物(需求/架构/测试/部署等)所有类型都可见。"""
        common = {"requirement_spec", "tech_architecture", "test_report", "deploy_report"}
        for pt in ProjectType:
            assert common.issubset(DELIVERABLES_BY_TYPE[pt])


class TestDeliverablesForType:
    def test_returns_frozenset_for_static_site(self):
        result = deliverables_for_type(ProjectType.STATIC_SITE)
        assert result == DELIVERABLES_BY_TYPE[ProjectType.STATIC_SITE]

    def test_returns_frozenset_for_binary_app(self):
        result = deliverables_for_type(ProjectType.BINARY_APP)
        assert result == DELIVERABLES_BY_TYPE[ProjectType.BINARY_APP]


class TestIsDeliverableVisible:
    def test_app_code_visible_for_binary_app(self):
        assert is_deliverable_visible(ProjectType.BINARY_APP, "app_code") is True

    def test_app_code_invisible_for_static_site(self):
        assert is_deliverable_visible(ProjectType.STATIC_SITE, "app_code") is False

    def test_build_visible_for_binary_app(self):
        assert is_deliverable_visible(ProjectType.BINARY_APP, "build") is True

    def test_build_invisible_for_static_site(self):
        assert is_deliverable_visible(ProjectType.STATIC_SITE, "build") is False

    def test_common_deliverable_visible_for_all_types(self):
        for pt in ProjectType:
            assert is_deliverable_visible(pt, "requirement_spec") is True


class TestPhasesByType:
    """v6.9: 按项目类型裁剪可见阶段(当前两类型都全7阶段, 为后续类型裁剪预留)。"""

    def test_all_types_covered(self):
        for pt in ProjectType:
            assert pt in PHASES_BY_TYPE

    def test_both_types_full_phases(self):
        """当前两类型都全7阶段(差异在交付物, 非阶段)。"""
        from arc.domain.pipeline.value_objects import PhaseType

        all_phases = frozenset(pt.value for pt in PhaseType)
        for pt in ProjectType:
            assert PHASES_BY_TYPE[pt] == all_phases


class TestProcessConfig:
    """v6.15: ProcessConfig 死字段清理后, 退化为 constraint 序列化容器。"""

    def test_only_constraint_field(self):
        """原 gate_strictness/auto_extract/require_explicit_confirm/show_phase_ui
        四字段前后端零业务消费, 已删除 — 仅 constraint 残留。"""
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(ProcessConfig)}
        dead = {
            "gate_strictness", "auto_extract",
            "require_explicit_confirm", "show_phase_ui",
        }
        assert dead.isdisjoint(field_names), f"死字段残留: {dead & field_names}"
        assert field_names == {"constraint"}

    def test_to_dict_only_constraint(self):
        """to_dict 仅输出 constraint 单键 (防 4 字段回归)。"""
        cfg = ProcessConfig(constraint=ProcessConstraint.STRICT)
        assert cfg.to_dict() == {"constraint": "strict"}

    def test_from_dict_ignores_legacy_keys(self):
        """旧数据含已删字段时, from_dict 只取 constraint, 其余忽略不报错。"""
        legacy = {
            "constraint": "free",
            "gate_strictness": "moderate",  # legacy, 已删
            "auto_extract": False,          # legacy, 已删
        }
        cfg = ProcessConfig.from_dict(legacy)
        assert cfg.constraint == ProcessConstraint.FREE
