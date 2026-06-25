"""方法论 Provider — 按阶段和项目约束动态注入方法论指导。"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class MethodologyProvider:
    """根据当前阶段 + 项目 ProcessConstraint 注入方法论。

    三级差异:
    - strict: 完整方法论
    - moderate: 精简方法论
    - free: 不注入方法论
    """

    source = "methodology"

    def __init__(self, db: AsyncSession):
        self._db = db

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        if not request.todo:
            return []

        try:
            content = await self._build(request)
            if not content:
                return []

            return [ContextSegment(
                source=self.source,
                priority=2,
                content=content,
            )]
        except Exception:
            logger.debug("MethodologyProvider failed", exc_info=True)
            return []

    async def _build(self, request: ContextRequest) -> str:
        from arc.application.execution.constraint_policy import (
            get_methodology_prompt_for_constraint,
        )
        from arc.domain.project.value_objects import ProcessConstraint

        constraint = ProcessConstraint.FREE
        project = None
        if request.todo and request.todo.project_id:
            from arc.infrastructure.repositories.project import ProjectRepository
            project = await ProjectRepository(self._db).get_by_id(
                request.todo.project_id
            )
            if project:
                constraint = project.process_constraint

        phase = request.phase
        if not phase:
            return ""

        user_rounds = sum(
            1 for m in request.conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )

        methodology = get_methodology_prompt_for_constraint(
            constraint, phase, user_rounds,
            title=request.todo.title if request.todo else "",
            description=request.todo.description if request.todo else "",
        )

        # 原型工程化指导 — 按 project_type 注入 (prototype 未完成且在原型产出阶段)。
        # v5.5/5.6 此处为 pass 未注入, v5.9.0 接入 get_prototype_guide 让指导真正生效,
        # 同时建立 "按 project_type 取指导" 的调用链 (避免注册表成为死代码)。
        completed = request.completed_artifacts or []
        if (
            "prototype" not in completed
            and request.phase in ("ui_design", "development")
            and project is not None
        ):
            from arc.application.context.prompts import get_prototype_guide
            guide = get_prototype_guide(project.project_type)
            if guide:
                methodology = f"{methodology}\n\n{guide}" if methodology else guide

        return methodology
