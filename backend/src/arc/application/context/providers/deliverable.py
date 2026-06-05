"""交付物清单 Provider — 注入待产出和已完成的交付物信息。"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class DeliverableProvider:
    """注入交付物清单和已完成产出物摘要。"""

    source = "deliverable"

    def __init__(self, db: AsyncSession):
        self._db = db

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        if not request.todo:
            return []

        try:
            from arc.application.context.prompts import (
                ARTIFACT_SCHEMAS,
                build_deliverable_checklist,
            )
            from arc.domain.artifact.value_objects import ARTIFACT_LABELS, ArtifactType
            from arc.infrastructure.repositories.artifact import ArtifactRepository
            from arc.infrastructure.repositories.planning import DeliverableTrackerRepository

            tracker_repo = DeliverableTrackerRepository(self._db)
            artifact_repo = ArtifactRepository(self._db)

            tracker = await tracker_repo.get_by_todo_id(request.conversation.todo_id)
            required = tracker.required if tracker else []
            completed = [
                k
                for k, v in (tracker.deliverables if tracker else {}).items()
                if v.value in ("produced", "confirmed")
            ]

            # 交付物清单
            checklist = build_deliverable_checklist(required, completed)
            schemas = "\n".join(
                f"- **{ARTIFACT_LABELS.get(ArtifactType(t), t)}** (`{t}`):"
                f"\n```\n{ARTIFACT_SCHEMAS.get(t, '{}')}\n```"
                for t in required
                if t not in completed
            )
            deliverable_section = (
                f"## 交付物清单（渐进式完成）\n{checklist}\n\n"
                "## 交付物输出规则\n"
                "当你认为某个交付物内容已经充分时，使用以下格式输出：\n\n"
                "[DELIVERABLE:artifact_type]\n```json\n(结构化内容)\n```\n\n"
                f"可用的artifact_type及其schema：\n{schemas}"
            )

            segments = [ContextSegment(
                source=self.source,
                priority=0,  # 不可压缩 — 核心指令
                content=deliverable_section,
            )]

            # 已完成产出物摘要
            completed_text = await self._build_completed_summary(
                artifact_repo, request.conversation.todo_id, completed
            )
            if completed_text:
                segments.append(ContextSegment(
                    source=self.source,
                    priority=2,
                    content=f"## 已完成的交付物\n{completed_text}",
                ))

            return segments
        except Exception:
            logger.debug("DeliverableProvider failed", exc_info=True)
            return []

    async def _build_completed_summary(
        self, artifact_repo, todo_id: uuid.UUID, completed: list[str]
    ) -> str:
        if not completed:
            return ""
        from arc.domain.artifact.value_objects import ARTIFACT_LABELS

        artifacts = await artifact_repo.list_by_todo_id(todo_id)
        parts = []
        for a in artifacts:
            if a.artifact_type.value in completed:
                label = ARTIFACT_LABELS.get(a.artifact_type, a.artifact_type.value)
                summary = json.dumps(a.content, ensure_ascii=False, indent=2)
                if len(summary) > 500:
                    summary = summary[:500] + "..."
                parts.append(f"### {label}\n{summary}")
        return "\n\n".join(parts) if parts else ""
