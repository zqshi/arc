"""ui_design_methodology 单测 — UI 设计产出物质量校验。

覆盖 validate_ui_design:
- wireframe 缺 user_story 标注检查
- 三态 gap 检查 (empty/loading/error, 含 v6.4 T5 补的 error state gap)

domain 层零 mock, 直接构造 content dict 验证行为。
"""
from arc.application.execution.ui_design_methodology import validate_ui_design


class TestValidateUiDesignWireframeStory:
    """wireframe 必须标注关联的 user_story。"""

    def test_wireframe_missing_story_emits_gap(self):
        """wireframe 无 story_id 且无 user_story → gap。"""
        content = {"wireframes": [{"page_name": "首页"}]}
        gaps = validate_ui_design(content)
        assert any("首页" in g and "user_story" in g for g in gaps)

    def test_wireframe_with_story_id_no_gap(self):
        """wireframe 有 story_id → 无 user_story gap。"""
        content = {"wireframes": [{"page_name": "首页", "story_id": "US-1"}]}
        gaps = validate_ui_design(content)
        assert not any("user_story" in g for g in gaps)

    def test_wireframe_with_user_story_field_no_gap(self):
        """wireframe 有 user_story 字段 → 无 gap。"""
        content = {"wireframes": [{"page_name": "首页", "user_story": "作为用户"}]}
        gaps = validate_ui_design(content)
        assert not any("user_story" in g for g in gaps)

    def test_wireframe_unnamed_shows_default(self):
        """wireframe 无 page_name → gap 显示「未命名」。"""
        content = {"wireframes": [{}]}
        gaps = validate_ui_design(content)
        assert any("未命名" in g for g in gaps)

    def test_non_dict_wireframe_skipped(self):
        """非 dict 的 wireframe 跳过(不报错)。"""
        content = {"wireframes": ["not a dict", {"page_name": "首页"}]}
        gaps = validate_ui_design(content)
        # 第二个无 story → 1 个 gap, 第一个不报错
        assert any("首页" in g for g in gaps)


class TestValidateUiDesignStates:
    """三态 gap 检查: empty/loading/error。

    v6.4 T5 补了 error state gap(原只有 empty/loading), 本组验证三态对称完整。
    """

    def test_all_three_states_missing_emits_three_gaps(self):
        """有 wireframes 但 component_specs 无任何状态 → 3 个 gap。"""
        content = {
            "wireframes": [{"page_name": "首页", "story_id": "US-1"}],
            "component_specs": [{"states": "默认"}],
        }
        gaps = validate_ui_design(content)
        assert any("空状态" in g for g in gaps)
        assert any("加载状态" in g for g in gaps)
        assert any("错误状态" in g for g in gaps)

    def test_all_three_states_present_no_state_gaps(self):
        """三态全有 → 无三态 gap。"""
        content = {
            "wireframes": [{"page_name": "首页", "story_id": "US-1"}],
            "component_specs": [{"states": "空状态/加载中/错误态"}],
        }
        gaps = validate_ui_design(content)
        assert not any("状态" in g for g in gaps)

    def test_english_state_keywords_detected(self):
        """英文 empty/loading/error 关键词也能检测。"""
        content = {
            "wireframes": [{"page_name": "首页", "story_id": "US-1"}],
            "component_specs": [{"states": "empty loading error"}],
        }
        gaps = validate_ui_design(content)
        assert not any("状态" in g for g in gaps)

    def test_only_error_state_present(self):
        """只有 error 态 → empty/loading 缺 → 2 个 gap(error 不缺)。

        重点验证 v6.4 T5 补的 error gap 逻辑: error 检测到则不报 error gap。
        """
        content = {
            "wireframes": [{"page_name": "首页", "story_id": "US-1"}],
            "component_specs": [{"states": "error"}],
        }
        gaps = validate_ui_design(content)
        assert any("空状态" in g for g in gaps)
        assert any("加载状态" in g for g in gaps)
        assert not any("错误状态" in g for g in gaps)

    def test_no_wireframes_skips_state_check(self):
        """无 wireframes → 三态不检查(前提是 wireframes 存在)。"""
        content = {"component_specs": [{"states": "默认"}]}
        gaps = validate_ui_design(content)
        assert not any("状态" in g for g in gaps)

    def test_non_dict_component_spec_skipped(self):
        """非 dict 的 component_spec 跳过(不报错)。"""
        content = {
            "wireframes": [{"page_name": "首页", "story_id": "US-1"}],
            "component_specs": ["not a dict"],
        }
        # 非 dict 跳过, 三态全缺 → 3 个 gap (不因非 dict 报错)
        gaps = validate_ui_design(content)
        assert len([g for g in gaps if "状态" in g]) == 3


class TestValidateUiDesignClean:
    """合规内容无 gap。"""

    def test_clean_content_no_gaps(self):
        """wireframe 有 story + 三态全有 → 无 gap。"""
        content = {
            "wireframes": [{"page_name": "首页", "story_id": "US-1"}],
            "component_specs": [{"states": "空/加载/错误"}],
        }
        assert validate_ui_design(content) == []

    def test_empty_content_no_gaps(self):
        """空 content → 无 gap(无 wireframes 不检查)。"""
        assert validate_ui_design({}) == []
