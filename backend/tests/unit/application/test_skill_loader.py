"""Tests for SkillLoader (v6.8.0 W2.2)."""
from __future__ import annotations

import uuid

from arc.application.capability.skill_loader import SkillLoader
from arc.domain.capability.value_objects import Capability, CapabilityType


def _skill(config: dict) -> Capability:
    return Capability(
        id=uuid.uuid4(), name="test-skill", type=CapabilityType.SKILL, config=config
    )


class TestSkillLoader:
    def test_load_with_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "ui-design"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: ui-design\ndescription: UI 设计规范\n---\n设计原则\n",
            encoding="utf-8",
        )
        loader = SkillLoader()
        section = loader.load(_skill({"directory": str(skill_dir)}))
        assert section == "ui-design: UI 设计规范\n设计原则"

    def test_load_without_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "plain"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("纯 prompt body\n", encoding="utf-8")
        loader = SkillLoader()
        section = loader.load(_skill({"directory": str(skill_dir)}))
        assert section == "skill\n纯 prompt body"

    def test_frontmatter_without_description(self, tmp_path):
        skill_dir = tmp_path / "nodesc"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: only-name\n---\nbody\n", encoding="utf-8"
        )
        loader = SkillLoader()
        section = loader.load(_skill({"directory": str(skill_dir)}))
        assert section == "only-name\nbody"

    def test_directory_not_exists(self):
        loader = SkillLoader()
        assert loader.load(_skill({"directory": "/nonexistent-path-xyz"})) is None

    def test_no_directory_config(self):
        loader = SkillLoader()
        assert loader.load(_skill({})) is None

    def test_skill_md_not_exists(self, tmp_path):
        loader = SkillLoader()
        # 目录存在但无 SKILL.md
        assert loader.load(_skill({"directory": str(tmp_path)})) is None

    def test_non_skill_type_returns_none(self, tmp_path):
        cap = Capability(
            id=uuid.uuid4(),
            name="agent-x",
            type=CapabilityType.AGENT,
            config={"directory": str(tmp_path)},
        )
        loader = SkillLoader()
        assert loader.load(cap) is None

    def test_unclosed_frontmatter_degrades(self, tmp_path):
        skill_dir = tmp_path / "unclosed"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: x\ndescription: 缺闭合\nbody 未结束\n", encoding="utf-8"
        )
        loader = SkillLoader()
        section = loader.load(_skill({"directory": str(skill_dir)}))
        # 无闭合 --- → 降级为纯 body (全文)
        assert section == "skill\n---\nname: x\ndescription: 缺闭合\nbody 未结束"


class TestSkillLoaderInline:
    """v6.9: skill 内联来源(config.source=inline, 直接填内容, 无需 SKILL.md 文件)。"""

    def test_inline_with_frontmatter(self):
        cap = _skill({
            "source": "inline",
            "content": "---\nname: inline-skill\ndescription: 内联\n---\n内联body\n",
        })
        section = SkillLoader().load(cap)
        assert section == "inline-skill: 内联\n内联body"

    def test_inline_plain(self):
        cap = _skill({"source": "inline", "content": "纯内联prompt"})
        section = SkillLoader().load(cap)
        assert section == "skill\n纯内联prompt"

    def test_inline_empty_returns_none(self):
        cap = _skill({"source": "inline", "content": ""})
        assert SkillLoader().load(cap) is None

    def test_inline_missing_content_returns_none(self):
        cap = _skill({"source": "inline"})
        assert SkillLoader().load(cap) is None

    def test_directory_source_still_works(self, tmp_path):
        """source=directory 显式声明, 走目录加载(向后兼容)。"""
        skill_dir = tmp_path / "explicit"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: explicit\ndescription: 显式\n---\nbody\n", encoding="utf-8"
        )
        cap = _skill({"source": "directory", "directory": str(skill_dir)})
        section = SkillLoader().load(cap)
        assert section == "explicit: 显式\nbody"
