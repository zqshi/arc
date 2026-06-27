"""content/methodology 模块测试 (T2/B方案) — 内容显性化 + .get fallback。

验证 methodology 内容从 constraint_policy / prompts 迁入 content 模块后:
- FREE_BASELINES / MODERATE_PROMPTS 已注册 phase 返回非空, 未注册返回空串
- get_prototype_guide 已注册 project_type 返回指导, 未注册返回空
- 关键文案存在 (逐字迁移正确性, 防 prompt 文本在迁移中被改写)
"""

from __future__ import annotations

from arc.application.context.content.methodology import (
    FREE_BASELINES,
    MODERATE_PROMPTS,
    PROTOTYPE_BUILD_GUIDES,
    get_prototype_guide,
)
from arc.domain.project.value_objects import ProjectType


class TestFreeBaselines:
    """free 模式质量底线 (by phase) — .get fallback。"""

    def test_registered_phases_return_non_empty(self):
        for phase in (
            "clarification", "ui_design", "architecture",
            "development", "testing", "deployment", "extraction",
        ):
            assert FREE_BASELINES.get(phase, "") != "", f"{phase} baseline 不应为空"

    def test_unregistered_phase_returns_empty(self):
        assert FREE_BASELINES.get("unknown_phase", "") == ""

    def test_clarification_baseline_has_quality_marker(self):
        assert "质量底线" in FREE_BASELINES["clarification"]


class TestModeratePrompts:
    """moderate 精简 prompt (by phase) — .get fallback。"""

    def test_registered_phases_return_non_empty(self):
        for phase in ("clarification", "ui_design", "architecture", "development", "testing"):
            assert MODERATE_PROMPTS.get(phase, "") != "", f"{phase} moderate prompt 不应为空"

    def test_unregistered_phase_returns_empty(self):
        assert MODERATE_PROMPTS.get("unknown_phase", "") == ""

    def test_clarification_has_simplified_marker(self):
        assert "精简模式" in MODERATE_PROMPTS["clarification"]


class TestGetPrototypeGuide:
    """原型指导 (by project_type) — 复用 v6.9 .get fallback 模式。"""

    def test_static_site_returns_engineering_guide(self):
        guide = get_prototype_guide(ProjectType.STATIC_SITE)
        assert guide  # 非空
        assert "前端工程" in guide  # 逐字迁移关键文案

    def test_binary_app_returns_tauri_guide(self):
        guide = get_prototype_guide(ProjectType.BINARY_APP)
        assert guide
        assert "原生客户端" in guide or "tauri" in guide.lower()

    def test_unregistered_type_returns_empty(self):
        assert get_prototype_guide("library") == ""  # type: ignore[arg-type]

    def test_registry_dict_fallback(self):
        # 直接 dict 访问也走 .get fallback 模式 (DELIVERABLES_BY_TYPE 范式)
        assert PROTOTYPE_BUILD_GUIDES.get("static_site", "") != ""
        assert PROTOTYPE_BUILD_GUIDES.get("library", "") == ""
