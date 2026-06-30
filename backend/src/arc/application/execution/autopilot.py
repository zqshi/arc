"""Autopilot 自驾循环 — ExecutionEngine 的 mixin (v6.19 续7补技术债清理)。

从 execution_engine.py 抽出 run_autopilot (~153 行), 降低该文件规模 (483→~330)。
行为零变化: mixin 通过 self 访问宿主 ExecutionEngine 的 _db/_tracker_repo/_conv_repo/
_prompt_builder + generate_response_stream 方法; 调用方 svc.run_autopilot(conv) 不变。

为何用 mixin 而非独立类: run_autopilot 是 async generator, 强依赖 self.generate_response_stream
回调 + 多个 repo; 独立类需注入全部依赖 + 回调, 改协作模型风险高。mixin 是项目既有模式
(infrastructure/models 的 TimestampMixin), 纯文件移动零行为变化。
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, AsyncIterator

from arc.application.execution.execution_helpers import (
    collect_qualified_types as _collect_qualified_types,
)
from arc.application.execution.execution_helpers import (
    extract_experience as _extract_experience,
)
from arc.application.execution.execution_helpers import (
    find_gate_stuck as _find_gate_stuck,
)
from arc.application.execution.execution_helpers import (
    needs_user_input as _needs_user_input,
)
from arc.domain.todo.value_objects import MessageRole

if TYPE_CHECKING:
    from arc.domain.conversation.entity import Conversation

logger = logging.getLogger(__name__)


class AutopilotMixin:
    """run_autopilot 自驾循环。

    隐式契约: 宿主须提供 self._db / self._tracker_repo / self._conv_repo /
    self._prompt_builder 属性 + generate_response_stream 方法 (即 ExecutionEngine)。
    """

    async def run_autopilot(
        self,
        conversation: Conversation,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """自驾模式：持续生成直到任务完成或需要用户澄清。

        每轮结束后创建 checkpoint (Harness §11)。
        Wall-clock 超时保护：总时长超 10 分钟强制暂停。
        断点恢复：检测已有 checkpoint，从上次中断的 round 继续。
        """
        from arc.application.execution.checkpoint import CheckpointManager

        max_rounds = 12
        wall_timeout = 600  # 10 分钟总超时
        checkpoint_mgr = CheckpointManager(self._db)
        start = time.monotonic()

        def _observe_task(outcome: str) -> None:
            """autopilot 任务结束埋点 (各正常退出分支调用; 异常路径由调用方 log, 不在此记)。"""
            from arc.application.execution.metrics import AGENT_TASK_DURATION

            AGENT_TASK_DURATION.labels(outcome=outcome).observe(time.monotonic() - start)

        # --- 断点恢复：检测是否有未完成的 checkpoint ---
        start_round = 0
        try:
            resume_round = await checkpoint_mgr.get_resume_round(conversation.id)
            if resume_round > 0:
                tracker = await self._tracker_repo.get_by_todo_id(conversation.todo_id)
                if tracker and not tracker.is_complete:
                    start_round = resume_round
                    handoff = await checkpoint_mgr.restore_from_checkpoint(conversation.id)
                    if handoff:
                        # 注入恢复上下文作为 system message
                        recovery_msg = conversation.add_message(
                            role=MessageRole.SYSTEM,
                            content=handoff.to_prompt(),
                            metadata={
                                "checkpoint_recovery": True,
                                "resumed_from_round": resume_round,
                            },
                        )
                        await self._conv_repo.add_message(conversation.id, recovery_msg)
                        logger.info(
                            "autopilot.resumed conversation=%s from_round=%d",
                            conversation.id, resume_round,
                        )
                        yield {
                            "event": "autopilot_resumed",
                            "resumed_from_round": resume_round,
                            "completed_items": handoff.completed,
                        }
        except Exception as exc:
            logger.warning("autopilot.restore_failed: %s", exc)

        max_gate_retries = 2
        last_stuck: str | None = None
        stuck_rounds = 0

        for round_num in range(start_round, max_rounds):
            # Wall-clock 超时检测
            elapsed = time.monotonic() - start
            if elapsed > wall_timeout:
                logger.warning(
                    "autopilot.wall_timeout conversation=%s elapsed=%.0fs",
                    conversation.id, elapsed,
                )
                _observe_task("timeout")
                yield {
                    "event": "autopilot_paused",
                    "reason": "wall_timeout",
                    "elapsed_seconds": int(elapsed),
                }
                return

            async for chunk in self.generate_response_stream(conversation, **kwargs):
                yield chunk

            tracker = await self._tracker_repo.get_by_todo_id(conversation.todo_id)
            qualified = await _collect_qualified_types(self._db, conversation.todo_id)

            # Checkpoint: 每轮结束创建状态快照 (基于质量达标，非虚假 produced)
            try:
                await checkpoint_mgr.create_checkpoint(
                    conversation.id,
                    state={
                        "round": round_num + 1,
                        "completed": sorted(qualified),
                        "completion_pct": tracker.completion_pct if tracker else 0,
                    },
                    label=f"autopilot-round-{round_num + 1}",
                )
            except Exception as exc:
                logger.warning("Checkpoint creation failed: %s", exc)

            # 质量达标完成 (非虚假完成——杜绝从劣质产出提炼经验)
            if tracker and tracker.is_quality_complete(qualified):
                await _extract_experience(self._db, conversation.todo_id, self._prompt_builder)
                _observe_task("complete")
                yield {
                    "event": "autopilot_complete",
                    "reason": "all_deliverables_quality_qualified",
                }
                return

            last_msg = conversation.messages[-1] if conversation.messages else None
            if last_msg and _needs_user_input(last_msg.content):
                _observe_task("paused")
                yield {"event": "autopilot_paused", "reason": "needs_user_input"}
                return

            # 门禁卡点检查: 有未通过质量门禁的产出物 → 反馈 gaps 让 LLM 修复 (而非盲目推进)
            stuck = await _find_gate_stuck(self._db, conversation.todo_id)
            if stuck:
                if stuck["type"] == last_stuck:
                    stuck_rounds += 1
                else:
                    last_stuck = stuck["type"]
                    stuck_rounds = 1
                if stuck_rounds > max_gate_retries:
                    _observe_task("paused")
                    yield {
                        "event": "autopilot_paused",
                        "reason": "gate_stuck",
                        "artifact": stuck["type"],
                        "gaps": stuck["gaps"][:3],
                    }
                    return
                advance_content = (
                    f"交付物「{stuck['label']}」未通过质量门禁："
                    f"{'; '.join(stuck['gaps'][:3])}。"
                    f"请据此完善后重新产出 [DELIVERABLE:{stuck['type']}]。"
                )
            else:
                last_stuck = None
                stuck_rounds = 0
                advance_content = "继续推进下一个阶段。"

            advance_msg = conversation.add_message(
                role=MessageRole.USER,
                content=advance_content,
                metadata={"auto_advance": True, "round": round_num + 1, "gate_retry": bool(stuck)},
            )
            await self._conv_repo.add_message(conversation.id, advance_msg)

        _observe_task("paused")
        yield {"event": "autopilot_paused", "reason": "max_rounds_reached"}
