"""Tests for CONVENTION_TEMPLATES 注册表 + ConventionTemplateRegistry (v6.3.0 T2)。

T2 按 ProjectType 裁剪治理规范: 已注册类型 = 通用骨架 + 类型特化段落;
未注册类型 = 仅通用骨架 (graceful fallback)。与 v5.9.0 get_prototype_guide 同构。

关键约束: 特化段落必须意图驱动, 禁规则执行式硬规则; 不同类型产出不同 charter。
"""

from arc.application.project.convention_templates import (
    CONVENTION_TEMPLATES,
    ConventionTemplateRegistry,
)
from arc.domain.project.charter import DefaultConventionTemplateProvider
from arc.domain.project.entity import Project
from arc.domain.project.value_objects import ProjectType


class TestConventionTemplateRegistry:
    def setup_method(self):
        self.registry = ConventionTemplateRegistry()

    def test_static_site_has_specialization(self):
        md = self.registry.get_template(ProjectType.STATIC_SITE)
        assert "静态站点特化治理意图" in md
        assert "可发现性意图" in md  # SEO
        assert "离线降级意图" in md  # PWA
        assert "加载体验意图" in md  # 性能

    def test_binary_app_has_specialization(self):
        md = self.registry.get_template(ProjectType.BINARY_APP)
        assert "原生客户端特化治理意图" in md
        assert "可信分发意图" in md  # 签名
        assert "渠道上架意图" in md  # 分发
        assert "跨平台一致性意图" in md

    def test_different_types_produce_different_charters(self):
        """不同 ProjectType 产出不同 charter (T4 核心验证项的前置)。"""
        static = self.registry.get_template(ProjectType.STATIC_SITE)
        binary = self.registry.get_template(ProjectType.BINARY_APP)
        assert static != binary
        assert "静态站点特化治理意图" in static
        assert "静态站点特化治理意图" not in binary
        assert "原生客户端特化治理意图" in binary
        assert "原生客户端特化治理意图" not in static

    def test_specialization_appended_to_base(self):
        """特化段落追加在通用骨架后 (通用意图所有类型共享, 不重复)。"""
        base = DefaultConventionTemplateProvider().get_template(ProjectType.STATIC_SITE)
        static = self.registry.get_template(ProjectType.STATIC_SITE)
        assert static.startswith(base)  # 通用骨架在前
        # 精确验证拼接结构: base + 换行 + 特化段落
        specialization = CONVENTION_TEMPLATES[ProjectType.STATIC_SITE]
        assert static == f"{base}\n{specialization}"

    def test_registered_type_contains_base_intents(self):
        """特化类型仍含通用治理意图 (上下文加载/版本迭代/代码规范/质量守护)。"""
        md = self.registry.get_template(ProjectType.STATIC_SITE)
        assert "上下文加载意图" in md
        assert "版本迭代意图" in md
        assert "代码规范意图" in md
        assert "质量守护意图" in md

    def test_no_hard_rules_in_specializations(self):
        """特化段落禁规则执行式硬规则 (意图驱动约束)。"""
        forbidden = [
            "500 行", "500行", "800 行", "单文件行数上限",
            "必须 auth", "必须挂载 auth", "auth 依赖",
            "必修项", "npm run build",  # 构建命令属 PROTOTYPE_BUILD_GUIDES, 非 charter
        ]
        for pt in CONVENTION_TEMPLATES:
            md = self.registry.get_template(pt)
            for token in forbidden:
                assert token not in md, f"{pt.value} 特化含硬规则/构建命令: {token!r}"

    def test_all_active_types_registered(self):
        """当前激活的 ProjectType 都有特化模板 (static_site + binary_app)。"""
        active_types = {ProjectType.STATIC_SITE, ProjectType.BINARY_APP}
        assert set(CONVENTION_TEMPLATES.keys()) == active_types

    def test_fallback_uses_default_when_type_unregistered(self, monkeypatch):
        """未注册类型走 default provider (graceful fallback, 不抛)。"""
        monkeypatch.setattr(
            "arc.application.project.convention_templates.CONVENTION_TEMPLATES", {}
        )
        base = DefaultConventionTemplateProvider().get_template(ProjectType.STATIC_SITE)
        md = self.registry.get_template(ProjectType.STATIC_SITE)
        assert md == base  # 未注册 → 纯 default 骨架, 无特化段落


class TestProjectInitializeCharterWithRegistry:
    def test_static_site_charter_has_specialization(self):
        """Project 用 registry 初始化后, charter 含 static_site 特化。"""
        p = Project(name="t", project_type=ProjectType.STATIC_SITE)
        p.initialize_charter(ConventionTemplateRegistry())
        assert "静态站点特化治理意图" in p.charter.markdown

    def test_binary_app_charter_has_specialization(self):
        p = Project(name="t", project_type=ProjectType.BINARY_APP)
        p.initialize_charter(ConventionTemplateRegistry())
        assert "原生客户端特化治理意图" in p.charter.markdown

    def test_charter_project_type_matches_with_registry(self):
        """registry 产出 charter 的 project_type 仍匹配实体类型。"""
        p = Project(name="t", project_type=ProjectType.BINARY_APP)
        p.initialize_charter(ConventionTemplateRegistry())
        assert p.charter.project_type == ProjectType.BINARY_APP
