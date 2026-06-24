"""充分性提示 Provider — 需求阶段早期引导, 质量判断由 sufficiency_gate 门禁承担。

v6.0 #7 后职责分离:
- 本 provider (每轮注入, 零 LLM): 只做 <2 轮早期粗引导"别急于产出"
- sufficiency_gate (确认 requirement_spec 时, 1 次 LLM): 三维评估对话信息是否足够
不在每轮调 LLM (成本不可接受), 质量判断集中在产出门禁。
"""

from __future__ import annotations

import logging

from arc.application.context.protocol import ContextRequest, ContextSegment

logger = logging.getLogger(__name__)


class SufficiencyHintProvider:
    """需求阶段早期注入引导提示 (轻量, 不调 LLM)。"""

    source = "sufficiency"

    async def provide(self, request: ContextRequest) -> list[ContextSegment]:
        if not request.todo:
            return []

        # 只在需求澄清阶段、requirement_spec 未产出前起作用
        if "requirement_spec" in request.completed_artifacts:
            return []

        user_rounds = sum(
            1 for m in request.conversation.messages
            if hasattr(m.role, "value") and m.role.value == "user"
        )

        # 早期 (<2 轮) 粗引导: 别急于产出, 先收集目标用户/核心问题/功能方向。
        # 是否真的充分由 sufficiency_gate 在确认时判断, 此处不替 LLM 做质量判断。
        if user_rounds < 2:
            content = (
                "[提示] 需求阶段早期, 信息通常尚不充分。先引导用户说清楚: "
                "目标用户是谁、要解决什么问题、大致想做什么, 不要急于生成产出物。"
            )
            return [ContextSegment(
                source=self.source,
                priority=2,
                content=content,
            )]

        return []
