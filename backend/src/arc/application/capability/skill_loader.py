"""Skill 加载器 (v6.8.0 W2.2 / v6.17 工具集扩展).

从 skill 类型能力的 SKILL.md 解析为 SkillContent (prompt section + tool_specs),
供执行引擎按环节注入 (对话侧 ContextAssembler / 执行侧 TaskContextBuilder 共享)。

SKILL.md 格式 (Claude Code SKILL.md + v6.17 tools 扩展):

    ---
    name: skill-name
    description: 简述
    tools:                      # v6.17 可选, 工具集声明
      - name: search_docs        # inline function 工具
        description: 搜索文档
        parameters: {type: object, properties: {...}}
      - name: mcp_tool           # mcp 引用工具
        source: mcp
        server_ref: mcp-cap-id
    ---
    body (prompt 内容)

load() 返回 prompt section (向后兼容, 不含 tool_specs); load_full() 返回完整
SkillContent (prompt + tool_specs)。无 frontmatter 降级为纯 body; 无 tools 时空
列表。directory 不存在 / 无 SKILL.md / 非 skill 类型 → None (调用方 graceful skip)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from arc.domain.capability.value_objects import Capability, ToolSource, ToolSpec

_FRONTMATTER_DELIM = "---"


@dataclass(frozen=True)
class SkillContent:
    """skill 加载产物 (v6.17)。

    prompt_section: 注入 prompt 的规范文本 (向后兼容 load() 的输出)。
    tool_specs: skill 声明的工具集 (inline function / mcp 引用)。
    """

    prompt_section: str
    tool_specs: list[ToolSpec] = field(default_factory=list)


class SkillLoader:
    def load(self, capability: Capability) -> str | None:
        """向后兼容: 返回 prompt section (无 tool_specs)。

        v6.17: 内部委托 load_full, 仅取 prompt_section。需工具集的调用方应用 load_full。
        """
        content = self.load_full(capability)
        return content.prompt_section if content else None

    def load_full(self, capability: Capability) -> SkillContent | None:
        """完整加载 skill: prompt section + tool_specs (v6.17)。

        config.source 决定加载方式:
        - "inline": 内联文本, 直接用 config.content (无需 SKILL.md 文件)
        - "directory"/缺省: 读 {directory}/SKILL.md (向后兼容)

        非 skill 类型 / 无内容 / 文件缺失 → None (调用方 graceful skip)。
        """
        if not capability.is_skill:
            return None
        config = capability.config or {}
        if config.get("source") == "inline":
            raw = config.get("content")
        else:
            directory = config.get("directory")
            if not directory:
                return None
            skill_path = Path(directory) / "SKILL.md"
            if not skill_path.is_file():
                return None
            raw = skill_path.read_text(encoding="utf-8")
        if not raw:
            return None
        return self._to_content(raw)

    def _to_content(self, content: str) -> SkillContent:
        name, description, body, tools = _parse_skill_md(content)
        header = name or "skill"
        if description:
            prompt = f"{header}: {description}\n{body}"
        else:
            prompt = f"{header}\n{body}"
        return SkillContent(prompt_section=prompt, tool_specs=tools)


def _parse_skill_md(
    content: str,
) -> tuple[str | None, str | None, str, list[ToolSpec]]:
    """解析 SKILL.md → (name, description, body, tools)。

    无 frontmatter / 未闭合 → (None, None, 全文, [])。frontmatter 用 yaml 解析
    (支持 tools 嵌套结构); 解析失败降级为纯 body。
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        return None, None, content.strip(), []

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == _FRONTMATTER_DELIM:
            end_idx = i
            break
    if end_idx is None:
        return None, None, content.strip(), []

    frontmatter_text = "\n".join(lines[1:end_idx])
    try:
        meta = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return None, None, content.strip(), []
    if not isinstance(meta, dict):
        return None, None, content.strip(), []

    name = meta.get("name")
    description = meta.get("description")
    body = "\n".join(lines[end_idx + 1 :]).strip()
    tools = _parse_tools(meta.get("tools"))
    return name, description, body, tools


def _parse_tools(raw: object) -> list[ToolSpec]:
    """从 frontmatter tools 字段解析 ToolSpec 列表 (v6.17)。

    每项: {name, description?, source?, parameters?, server_ref?}。
    source 缺省 inline; 非法值降级 inline。无 name / 非 dict 项跳过。
    """
    if not isinstance(raw, list):
        return []
    specs: list[ToolSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name or not str(name).strip():
            continue
        source_raw = item.get("source") or "inline"
        try:
            source = ToolSource(source_raw)
        except ValueError:
            source = ToolSource.INLINE
        desc = item.get("description") or ""
        ref = item.get("server_ref") or ""
        params = item.get("parameters")
        params = params if isinstance(params, dict) else {}
        try:
            specs.append(
                ToolSpec(
                    name=str(name).strip(),
                    description=str(desc),
                    source=source,
                    parameters=params,
                    server_ref=str(ref),
                )
            )
        except Exception:
            continue
    return specs
