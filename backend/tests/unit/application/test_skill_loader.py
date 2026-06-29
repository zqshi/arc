"""Tests for SkillLoader (v6.8.0 W2.2)."""
from __future__ import annotations

import uuid

from arc.application.capability.skill_loader import SkillLoader
from arc.domain.capability.value_objects import (
    Capability,
    CapabilityType,
    ToolSource,
)


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


class TestSkillLoaderTools:
    """v6.17: load_full 返回 SkillContent (prompt + tool_specs)。"""

    def test_load_full_with_inline_tools(self, tmp_path):
        skill_dir = tmp_path / "dev-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: dev-skill\n"
            "description: 开发规范\n"
            "tools:\n"
            "  - name: search_docs\n"
            "    description: 搜索文档\n"
            "    parameters:\n"
            "      type: object\n"
            "---\n"
            "body 规范\n",
            encoding="utf-8",
        )
        content = SkillLoader().load_full(_skill({"directory": str(skill_dir)}))
        assert content is not None
        assert content.prompt_section == "dev-skill: 开发规范\nbody 规范"
        assert len(content.tool_specs) == 1
        tool = content.tool_specs[0]
        assert tool.name == "search_docs"
        assert tool.is_inline
        assert tool.parameters == {"type": "object"}

    def test_load_full_with_mcp_tool(self, tmp_path):
        skill_dir = tmp_path / "mcp-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: mcp-skill\n"
            "tools:\n"
            "  - name: mcp_tool\n"
            "    source: mcp\n"
            "    server_ref: mcp-cap-123\n"
            "---\n"
            "body\n",
            encoding="utf-8",
        )
        content = SkillLoader().load_full(_skill({"directory": str(skill_dir)}))
        assert content is not None
        assert len(content.tool_specs) == 1
        tool = content.tool_specs[0]
        assert tool.is_mcp
        assert tool.server_ref == "mcp-cap-123"

    def test_load_full_no_tools_empty_list(self, tmp_path):
        skill_dir = tmp_path / "plain"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: plain\ndescription: 无工具\n---\nbody\n", encoding="utf-8"
        )
        content = SkillLoader().load_full(_skill({"directory": str(skill_dir)}))
        assert content is not None
        assert content.tool_specs == []

    def test_load_full_inline_source_with_tools(self):
        cap = _skill(
            {
                "source": "inline",
                "content": (
                    "---\nname: inline-skill\ntools:\n"
                    "  - name: t1\n    description: 工具1\n"
                    "---\nbody\n"
                ),
            }
        )
        content = SkillLoader().load_full(cap)
        assert content is not None
        assert len(content.tool_specs) == 1
        assert content.tool_specs[0].name == "t1"

    def test_load_backwards_compatible_returns_str(self, tmp_path):
        """load() 仍返回 str (向后兼容, 不含 tool_specs)。"""
        skill_dir = tmp_path / "compat"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: compat\ndescription: 兼容\n---\nbody\n", encoding="utf-8"
        )
        section = SkillLoader().load(_skill({"directory": str(skill_dir)}))
        assert section == "compat: 兼容\nbody"
        assert isinstance(section, str)

    def test_load_full_invalid_tool_source_falls_back_inline(self, tmp_path):
        skill_dir = tmp_path / "bad-source"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: bad\ntools:\n  - name: t\n    source: unknown\n---\nbody\n",
            encoding="utf-8",
        )
        content = SkillLoader().load_full(_skill({"directory": str(skill_dir)}))
        assert content is not None
        assert content.tool_specs[0].source == ToolSource.INLINE

    def test_load_full_skips_tool_without_name(self, tmp_path):
        skill_dir = tmp_path / "no-name"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: nn\ntools:\n  - description: 无名\n---\nbody\n",
            encoding="utf-8",
        )
        content = SkillLoader().load_full(_skill({"directory": str(skill_dir)}))
        assert content is not None
        assert content.tool_specs == []

    def test_load_full_non_skill_returns_none(self):
        cap = Capability(
            id=uuid.uuid4(),
            name="agent",
            type=CapabilityType.AGENT,
            config={"source": "inline", "content": "x"},
        )
        assert SkillLoader().load_full(cap) is None
