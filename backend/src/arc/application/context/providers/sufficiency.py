"""充分性提示 Provider — 需求阶段信息不足时给出引导。"""

from __future__ import annotations

import logging

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class SufficiencyHintProvider:
    """在需求阶段早期注入引导提示。

    轻量版: 不调用 LLM，基于对话轮次给出定性提示。
    """

    source = "sufficiency"

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        if not request.todo:
            return []

        # 只在需求澄清阶段起作用
        if "requirement_spec" in request.completed_artifacts:
            return []

        user_rounds = sum(
            1 for m in request.conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )

        if user_rounds < 2:
            content = (
                "[提示] 当前信息尚不充分，请先引导用户说清楚：目标用户是谁、"
                "要解决什么问题、大致想做什么。不要急于生成产出物。"
            )
        elif user_rounds < 4:
            content = (
                "[提示] 基本信息已初步收集，但可能仍有模糊点。"
                "继续追问以确保信息充分后再产出交付物。"
            )
        else:
            return []

        return [ContextSegment(
            source=self.source,
            priority=2,
            content=content,
        )]
