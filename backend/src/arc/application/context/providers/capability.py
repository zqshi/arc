"""能力注入 Provider (v6.8.0 W3.2 / v6.17 执行侧注入).

按当前环节取项目 phase_capabilities 配置的能力:
- skill 类型 → SkillLoader.load_full 加载 SKILL.md 为 prompt section + tool_specs
- agent 类型 → "可用 agent: X" 轻量提示 (实际调度仍由 AgentRegistry, 不改运行时选配)

两条注入路径共享 _collect_active_caps (单一真相源):
- provide(): 对话侧 (ContextAssembler), 拼 segment content (prompt section + agent 提示)
- load_phase_skills(): 执行侧 (TaskContextBuilder), 返回结构化 (prompts, tool_specs)

无配置 / 能力全禁用 / skill 文件缺失 → 返回空 (不污染 prompt / 不注入执行)。
异常包裹返回空 (Provider 契约: 不阻断 prompt 组装 / 不阻断 agent 执行)。
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment
from arc.domain.capability.value_objects import Capability, ToolSpec

logger = logging.getLogger(__name__)


class CapabilityProvider:
    """按环节注入已配置的能力 (skill 内容 + agent 提示)。"""

    source = "capability"

    def __init__(self, db: AsyncSession):
        self._db = db

    async def _collect_active_caps(
        self, project_id: uuid.UUID, phase: str
    ) -> list[Capability]:
        """取某环节已配置且启用的能力 (v6.17 抽出, 对话/执行共享)。

        读 project.pipeline_config.phase_capabilities[phase] →
        CapabilityService.list_by_ids → 过滤 active。无配置/无启用 → 空列表。
        """
        from arc.application.capability.service import CapabilityService
        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(self._db).get_by_id(project_id)
        if not project:
            return []
        phase_caps = (project.pipeline_config or {}).get("phase_capabilities") or {}
        cap_ids = phase_caps.get(phase)
        if not cap_ids:
            return []

        uuids: list[uuid.UUID] = []
        for cid in cap_ids:
            try:
                uuids.append(uuid.UUID(cid) if isinstance(cid, str) else cid)
            except (ValueError, AttributeError):
                logger.warning(
                    "invalid capability_id in phase_capabilities[%s]: %s",
                    phase, cid,
                )
        if not uuids:
            return []

        caps = await CapabilityService(self._db).list_by_ids(uuids)
        return [c for c in caps if c.is_active]

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        """对话侧注入: skill prompt section + agent 提示 (拼为 segment content)。"""
        if not request.todo or not request.project_id:
            return []
        try:
            from arc.application.capability.skill_loader import SkillLoader

            active = await self._collect_active_caps(request.project_id, request.phase)
            if not active:
                return []

            loader = SkillLoader()
            sections: list[str] = []
            for cap in active:
                if cap.is_skill:
                    content = loader.load_full(cap)
                    if content:
                        sections.append(content.prompt_section)
                elif cap.is_agent:
                    sections.append(f"- 可用 agent: {cap.name}")
            if not sections:
                return []

            return [ContextSegment(
                source=self.source,
                priority=1,
                content="## 本环节启用能力\n" + "\n".join(sections),
            )]
        except Exception:
            logger.warning("CapabilityProvider failed", exc_info=True)
            return []

    async def load_phase_skills(
        self, project_id: uuid.UUID, phase: str
    ) -> tuple[list[str], list[ToolSpec], list[dict]]:
        """执行侧注入 (v6.17): 取该环节 skill 规范 + 工具集 + MCP server 配置。

        与 provide 共享 _collect_active_caps:
        - skill 类型 → SkillLoader.load_full → prompt section + inline tools
        - mcp 类型 → McpLoader.load → mcp tool_specs + 连接配置 (供 adapter 注入)

        返回 (prompt_sections, tool_specs, mcp_servers) 供 TaskContextBuilder 注入。
        mcp_servers = [{name, transport, command/url, ...}] (ClaudeCode/OpenHands 用)。
        无能力 → ([], [], [])。异常 → ([], [], []) (不阻断 agent 执行)。
        """
        try:
            from arc.application.capability.mcp_loader import McpLoader
            from arc.application.capability.skill_loader import SkillLoader

            active = await self._collect_active_caps(project_id, phase)
            if not active:
                return [], [], []
            loader = SkillLoader()
            mcp_loader = McpLoader()
            prompts: list[str] = []
            tools: list[ToolSpec] = []
            mcp_servers: list[dict] = []
            for cap in active:
                if cap.is_skill:
                    content = loader.load_full(cap)
                    if content:
                        prompts.append(content.prompt_section)
                        tools.extend(content.tool_specs)
                elif cap.is_mcp:
                    tools.extend(await mcp_loader.load(cap))
                    mcp_servers.append({"name": cap.name, **(cap.config or {})})
            return prompts, tools, mcp_servers
        except Exception:
            logger.warning("load_phase_skills failed", exc_info=True)
            return [], [], []
