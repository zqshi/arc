"""能力注入 Provider (v6.8.0 W3.2).

按当前环节 (ContextRequest.phase) 取项目 phase_capabilities 配置的能力:
- skill 类型 → SkillLoader.load 加载 SKILL.md 为 prompt section (影响 AI 行为)
- agent 类型 → "可用 agent: X" 轻量提示 (实际调度仍由 AgentRegistry, 不改运行时选配)

无配置 / 能力全禁用 / skill 文件缺失 → 返回空 (不污染 prompt)。
异常包裹返回 [] (Provider 契约: 不阻断 prompt 组装)。
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class CapabilityProvider:
    """按环节注入已配置的能力 (skill 内容 + agent 提示)。"""

    source = "capability"

    def __init__(self, db: AsyncSession):
        self._db = db

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        if not request.todo or not request.project_id:
            return []
        try:
            from arc.application.capability.service import CapabilityService
            from arc.application.capability.skill_loader import SkillLoader
            from arc.infrastructure.repositories.project import ProjectRepository

            project = await ProjectRepository(self._db).get_by_id(request.project_id)
            if not project:
                return []
            phase_caps = (project.pipeline_config or {}).get("phase_capabilities") or {}
            cap_ids = phase_caps.get(request.phase)
            if not cap_ids:
                return []

            uuids: list[uuid.UUID] = []
            for cid in cap_ids:
                try:
                    uuids.append(uuid.UUID(cid) if isinstance(cid, str) else cid)
                except (ValueError, AttributeError):
                    logger.warning(
                        "invalid capability_id in phase_capabilities[%s]: %s",
                        request.phase, cid,
                    )
            if not uuids:
                return []

            caps = await CapabilityService(self._db).list_by_ids(uuids)
            active = [c for c in caps if c.is_active]
            if not active:
                return []

            loader = SkillLoader()
            sections: list[str] = []
            for cap in active:
                if cap.is_skill:
                    content = loader.load(cap)
                    if content:
                        sections.append(content)
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
