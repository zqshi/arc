"""Skill 加载器 (v6.8.0 W2.2).

从 skill 类型能力的 SKILL.md 解析为 prompt section, 供执行引擎按环节注入 (W3.2)。
格式 (Claude Code SKILL.md):

    ---
    name: skill-name
    description: 简述
    ---
    body (prompt 内容)

加载为 "{name}: {description}\\n{body}"。无 frontmatter 降级为 "{name or 'skill'}\\n{body}"。
directory 不存在 / 无 SKILL.md / 非 skill 类型 → None (调用方 graceful skip)。
"""
from __future__ import annotations

from pathlib import Path

from arc.domain.capability.value_objects import Capability

_FRONTMATTER_DELIM = "---"


class SkillLoader:
    def load(self, capability: Capability) -> str | None:
        """从 skill 能力加载 prompt section (SKILL.md 解析)。

        非 skill 类型 / 无 directory / 文件缺失 → None。
        """
        if not capability.is_skill:
            return None
        config = capability.config or {}
        directory = config.get("directory")
        if not directory:
            return None
        skill_path = Path(directory) / "SKILL.md"
        if not skill_path.is_file():
            return None
        content = skill_path.read_text(encoding="utf-8")
        return self._to_section(content)

    def _to_section(self, content: str) -> str:
        name, description, body = _parse_skill_md(content)
        header = name or "skill"
        if description:
            return f"{header}: {description}\n{body}"
        return f"{header}\n{body}"


def _parse_skill_md(content: str) -> tuple[str | None, str | None, str]:
    """解析 SKILL.md → (name, description, body)。无 frontmatter 时 body=全文。"""
    lines = content.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return None, None, content.strip()

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            end_idx = i
            break
    if end_idx is None:
        return None, None, content.strip()

    name: str | None = None
    description: str | None = None
    for line in lines[1:end_idx]:
        if line.startswith("name:"):
            name = line[len("name:") :].strip()
        elif line.startswith("description:"):
            description = line[len("description:") :].strip()
    body = "\n".join(lines[end_idx + 1 :]).strip()
    return name, description, body
