"""Tests for ProjectCharter 值对象 + ConventionTemplateProvider (v6.3.0 T1)。

charter 是项目初始化时按 ProjectType 产出的意图驱动治理规范, 与 conventions 并存。
T1 默认 provider 返回通用骨架 (T2 用 CONVENTION_TEMPLATES 注册表做类型特化)。

关键约束: 骨架必须意图驱动, 禁用 Arc 现有规则执行式硬规则 ("文件<500行"/"必须auth"等)。
"""

from dataclasses import FrozenInstanceError

from arc.domain.project.charter import (
    DefaultConventionTemplateProvider,
    ProjectCharter,
)
from arc.domain.project.entity import Project
from arc.domain.project.value_objects import ProjectType


def _sample_charter() -> ProjectCharter:
    return ProjectCharter(
        markdown="# 宪章\n内容",
        project_type=ProjectType.STATIC_SITE,
        template_version=1,
    )


class TestProjectCharter:
    def test_create_full_fields(self):
        c = _sample_charter()
        assert c.markdown == "# 宪章\n内容"
        assert c.project_type == ProjectType.STATIC_SITE
        assert c.template_version == 1
        assert c.created_at is not None  # default_factory

    def test_to_dict_from_dict_roundtrip(self):
        c = _sample_charter()
        d = c.to_dict()
        assert d["project_type"] == "static_site"
        back = ProjectCharter.from_dict(d)
        assert back is not None
        assert back.markdown == c.markdown
        assert back.project_type == ProjectType.STATIC_SITE
        assert back.template_version == c.template_version

    def test_from_dict_none_returns_none(self):
        assert ProjectCharter.from_dict(None) is None

    def test_from_dict_empty_dict_returns_none(self):
        assert ProjectCharter.from_dict({}) is None

    def test_from_dict_missing_fields_uses_defaults(self):
        """缺 template_version/created_at → 容错重建 (不抛)。"""
        back = ProjectCharter.from_dict({"markdown": "x", "project_type": "static_site"})
        assert back is not None
        assert back.template_version == 1
        assert back.created_at is None

    def test_from_dict_invalid_project_type_returns_none(self):
        """非法 project_type → None (容错, 不抛)。"""
        back = ProjectCharter.from_dict(
            {"markdown": "x", "project_type": "not_a_real_type"}
        )
        assert back is None

    def test_from_dict_not_dict_returns_none(self):
        assert ProjectCharter.from_dict("string") is None  # type: ignore[arg-type]
        assert ProjectCharter.from_dict(123) is None  # type: ignore[arg-type]

    def test_is_empty(self):
        assert ProjectCharter(
            markdown="", project_type=ProjectType.STATIC_SITE
        ).is_empty()
        assert ProjectCharter(
            markdown="   \n  ", project_type=ProjectType.STATIC_SITE
        ).is_empty()
        assert not _sample_charter().is_empty()

    def test_frozen_immutable(self):
        """frozen 值对象不可变, 改字段抛 FrozenInstanceError。"""
        c = _sample_charter()
        try:
            c.markdown = "changed"  # type: ignore[misc]
            assert False, "应抛 FrozenInstanceError"
        except FrozenInstanceError:
            pass


class TestDefaultConventionTemplateProvider:
    def setup_method(self):
        self.provider = DefaultConventionTemplateProvider()

    def test_get_template_nonempty(self):
        md = self.provider.get_template(ProjectType.STATIC_SITE)
        assert isinstance(md, str)
        assert len(md.strip()) > 100  # 骨架有实质内容

    def test_same_skeleton_for_all_types(self):
        """T1 通用骨架, 不按类型特化 (T2 才特化)。"""
        static = self.provider.get_template(ProjectType.STATIC_SITE)
        binary = self.provider.get_template(ProjectType.BINARY_APP)
        assert static == binary  # T1: 通用, 不分类型

    def test_no_hard_rules(self):
        """骨架禁用 Arc 规则执行式硬规则措辞 (意图驱动, 非阈值约束)。"""
        md = self.provider.get_template(ProjectType.STATIC_SITE)
        forbidden = [
            "500 行", "500行", "< 500", "800 行", "800行",
            "单文件行数上限", "必须 auth", "必须挂载 auth", "auth 依赖",
            "必修项", "6.1", "6.5",
        ]
        for token in forbidden:
            assert token not in md, f"骨架含硬规则措辞: {token!r}"

    def test_has_intent_driven_structure(self):
        """骨架含意图驱动结构标记 (目标/输出契约/上下文)。"""
        md = self.provider.get_template(ProjectType.STATIC_SITE)
        assert "目标" in md
        assert "输出契约" in md
        assert "上下文" in md

    def test_conveys_arc_governance_intents(self):
        """骨架传达 Arc 治理体系核心意图 (上下文加载/版本迭代/代码规范/质量守护)。"""
        md = self.provider.get_template(ProjectType.STATIC_SITE)
        assert "上下文加载" in md
        assert "版本迭代" in md
        assert "代码规范" in md
        assert "质量守护" in md


class TestProjectInitializeCharter:
    def test_initialize_sets_charter(self):
        p = Project(name="t")
        assert p.charter is None
        p.initialize_charter(DefaultConventionTemplateProvider())
        assert p.charter is not None
        assert not p.charter.is_empty()

    def test_charter_project_type_matches(self):
        p = Project(name="t", project_type=ProjectType.BINARY_APP)
        p.initialize_charter(DefaultConventionTemplateProvider())
        assert p.charter.project_type == ProjectType.BINARY_APP

    def test_initialize_overwrites(self):
        """重复 initialize 覆盖旧 charter (类型变更/模板升级时重新生成)。"""
        p = Project(name="t", project_type=ProjectType.STATIC_SITE)
        p.initialize_charter(DefaultConventionTemplateProvider())
        first = p.charter
        assert first is not None

        p.project_type = ProjectType.BINARY_APP
        p.initialize_charter(DefaultConventionTemplateProvider())
        assert p.charter is not None
        assert p.charter is not first  # 新实例 (frozen, 不可变所以必新建)
        assert p.charter.project_type == ProjectType.BINARY_APP

    def test_initialize_with_default_provider_independent(self):
        """provider 无状态, 多个项目各自 initialize 互不影响。"""
        provider = DefaultConventionTemplateProvider()
        p1 = Project(name="a", project_type=ProjectType.STATIC_SITE)
        p2 = Project(name="b", project_type=ProjectType.BINARY_APP)
        p1.initialize_charter(provider)
        p2.initialize_charter(provider)
        assert p1.charter.project_type == ProjectType.STATIC_SITE
        assert p2.charter.project_type == ProjectType.BINARY_APP
