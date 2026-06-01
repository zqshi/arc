"""执行引擎 — 对话模式的流式执行编排。

从 conversation_strategy.py 提取。职责：
- Tool-aware / Text-only 双路径分发
- Autopilot 自动推进循环
- SSE 事件流映射
- AI 消息持久化 + 交付物提取
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, AsyncIterator

from arc.domain.artifact.value_objects import ARTIFACT_LABELS
from arc.domain.todo.value_objects import MessageRole

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from arc.application.context.prompt_builder import PromptBuilder
    from arc.application.execution.artifact_extractor import ArtifactExtractor
    from arc.domain.conversation.entity import Conversation
    from arc.infrastructure.repositories.conversation import ConversationRepository
    from arc.infrastructure.repositories.planning import DeliverableTrackerRepository

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """编排 LLM 流式执行，支持 tool-use / text-only / 多 Agent 三种路径。

    集成:
    - HookManager (Harness §12) — 7 注入点的扩展管道
    - CheckpointManager (Harness §11) — autopilot 里程碑快照
    """

    def __init__(
        self,
        db: AsyncSession,
        prompt_builder: PromptBuilder,
        conv_repo: ConversationRepository,
        tracker_repo: DeliverableTrackerRepository,
        extractor: ArtifactExtractor,
    ):
        self._db = db
        self._prompt_builder = prompt_builder
        self._conv_repo = conv_repo
        self._tracker_repo = tracker_repo
        self._extractor = extractor

        # Harness §12: Hook Manager
        from arc.application.hooks.manager import HookManager
        self._hooks = HookManager()

    @property
    def hooks(self):
        """暴露 HookManager 供外部注册 hooks。"""
        return self._hooks

    async def generate_response_stream(
        self,
        conversation: Conversation,
        *,
        project_path: str | None = None,
        sandbox_policy=None,
        orchestration_enabled: bool = False,
    ) -> AsyncIterator[dict]:
        """生成 AI 流式回复。"""
        from arc.application.hooks.manager import HookPoint

        # Hook: pre_input
        hook_ctx = await self._hooks.trigger(HookPoint.PRE_INPUT, {
            "conversation_id": str(conversation.id),
            "message_count": len(conversation.messages),
        })

        # Hook: pre_llm
        await self._hooks.trigger(HookPoint.PRE_LLM, {
            "conversation_id": str(conversation.id),
            "project_path": project_path,
        })

        llm_messages = await self._prompt_builder.build_llm_messages(conversation)

        message_id: str | None = None
        full_content = ""
        loop_metrics: dict = {}

        if project_path:
            async for event_dict in self._tool_aware_stream(
                llm_messages, project_path, sandbox_policy, orchestration_enabled,
            ):
                if "message_id" in event_dict and event_dict.get("content"):
                    if message_id is None:
                        message_id = event_dict["message_id"]
                    full_content += event_dict["content"]
                if event_dict.get("event") == "complete_metrics":
                    loop_metrics = event_dict.get("metrics", {})
                    continue
                yield event_dict
        else:
            async for event_dict in self._text_only_stream(
                llm_messages, conversation.todo_id,
            ):
                if "message_id" in event_dict and event_dict.get("content"):
                    if message_id is None:
                        message_id = event_dict["message_id"]
                    full_content += event_dict["content"]
                if event_dict.get("event") == "complete_metrics":
                    loop_metrics = event_dict.get("metrics", {})
                    continue
                yield event_dict

        if not message_id:
            message_id = str(uuid.uuid4())

        ai_message = conversation.add_message(
            role=MessageRole.ASSISTANT,
            content=full_content,
            metadata={
                "message_id": message_id,
                "streamed": True,
                "mode": "conversation",
                "agent_loop": loop_metrics,
            },
            id=uuid.UUID(message_id),
        )
        await self._conv_repo.add_message(conversation.id, ai_message)

        extracted = await self._extractor.process_message(
            full_content, conversation.todo_id,
        )
        if extracted:
            artifact_names = [
                ARTIFACT_LABELS.get(a.artifact_type, a.artifact_type.value)
                for a in extracted
            ]
            yield {
                "message_id": message_id,
                "event": "artifacts_extracted",
                "artifacts": [str(a.id) for a in extracted],
                "artifact_names": artifact_names,
            }
            tracker = await self._tracker_repo.get_by_todo_id(conversation.todo_id)
            if tracker and tracker.is_complete:
                await self._extract_experience(conversation.todo_id)

    async def run_autopilot(
        self,
        conversation: Conversation,
        **kwargs,
    ) -> AsyncIterator[dict]:
        """自驾模式：持续生成直到任务完成或需要用户澄清。

        每轮结束后创建 checkpoint (Harness §11)。
        """
        from arc.application.execution.checkpoint import CheckpointManager

        max_rounds = 12
        checkpoint_mgr = CheckpointManager(self._db)

        for round_num in range(max_rounds):
            async for chunk in self.generate_response_stream(conversation, **kwargs):
                yield chunk

            tracker = await self._tracker_repo.get_by_todo_id(conversation.todo_id)

            # Checkpoint: 每轮结束创建状态快照
            try:
                completed_items = []
                if tracker:
                    completed_items = [
                        k for k, v in tracker.deliverables.items()
                        if v.value in ("produced", "confirmed")
                    ]
                await checkpoint_mgr.create_checkpoint(
                    conversation.id,
                    state={
                        "round": round_num + 1,
                        "completed": completed_items,
                        "completion_pct": tracker.completion_pct if tracker else 0,
                    },
                    label=f"autopilot-round-{round_num + 1}",
                )
            except Exception as exc:
                logger.warning("Checkpoint creation failed: %s", exc)

            if tracker and tracker.is_complete:
                await self._extract_experience(conversation.todo_id)
                yield {"event": "autopilot_complete", "reason": "all_deliverables_done"}
                return

            last_msg = conversation.messages[-1] if conversation.messages else None
            if last_msg and _needs_user_input(last_msg.content):
                yield {"event": "autopilot_paused", "reason": "needs_user_input"}
                return

            advance_msg = conversation.add_message(
                role=MessageRole.USER,
                content="继续推进下一个阶段。",
                metadata={"auto_advance": True, "round": round_num + 1},
            )
            await self._conv_repo.add_message(conversation.id, advance_msg)

        yield {"event": "autopilot_paused", "reason": "max_rounds_reached"}

    # ------------------------------------------------------------------
    # Tool-aware execution path
    # ------------------------------------------------------------------

    async def _tool_aware_stream(
        self,
        llm_messages: list,
        project_path: str,
        sandbox_policy,
        orchestration_enabled: bool,
    ) -> AsyncIterator[dict]:
        from arc.application.ai.adapter_pool import adapter_pool
        from arc.application.context.compression import CompressionManager
        from arc.application.execution.drift_detector import DriftDetector
        from arc.application.execution.error_loop_detector import ErrorLoopDetector
        from arc.application.execution.tool_loop import ToolAwareLoop, ToolLoopEvent
        from arc.application.execution.tools import ToolRegistry

        registry = ToolRegistry(project_path)
        compression = CompressionManager()  # L1 不需要 LLM adapter

        # 从 llm_messages 提取用户目标用于漂移检测
        user_goal = ""
        for m in reversed(llm_messages):
            if m.role == "user":
                user_goal = m.content[:500]
                break

        drift_detector = DriftDetector(user_goal) if user_goal else None
        error_detector = ErrorLoopDetector()

        # Sandbox integration
        sandbox_runtime = None
        if sandbox_policy and sandbox_policy.mode.value != "none":
            from arc.application.sandbox.runtime import create_sandbox_runtime
            from arc.application.sandbox.tools import SandboxedToolRegistry

            sandbox_runtime = create_sandbox_runtime(
                sandbox_policy, project_path,
                emit_callback=lambda ev: None,
            )
            registry = SandboxedToolRegistry(project_path, sandbox_runtime)

        # Orchestration or single-agent
        if orchestration_enabled:
            from arc.application.orchestration.service import OrchestrationService

            orch = OrchestrationService(adapter_pool)
            event_stream = orch.execute(llm_messages, registry)
        else:
            async def _single():
                async with adapter_pool.acquire() as adapter:
                    loop = ToolAwareLoop(
                        adapter, registry,
                        compression=compression,
                        drift_detector=drift_detector,
                        error_loop_detector=error_detector,
                    )
                    async for ev in loop.run(llm_messages):
                        yield ev
            event_stream = _single()

        async for event in event_stream:
            for mapped in _map_tool_event(event):
                yield mapped

    # ------------------------------------------------------------------
    # Text-only execution path
    # ------------------------------------------------------------------

    async def _text_only_stream(
        self,
        llm_messages: list,
        todo_id: uuid.UUID,
    ) -> AsyncIterator[dict]:
        from arc.application.ai.adapter_pool import adapter_pool
        from arc.application.execution.agent_loop import (
            DELIVERABLE_REQUIRED_FIELDS,
            AgentLoop,
            DeliverableValidator,
            LoopConfig,
        )

        validator = DeliverableValidator(DELIVERABLE_REQUIRED_FIELDS)
        config = await self._build_loop_config(todo_id)

        message_id: str | None = None

        async with adapter_pool.acquire() as adapter:
            loop = AgentLoop(adapter, config)
            async for event in loop.run(llm_messages, validator=validator):
                if event.type == "chunk":
                    if message_id is None:
                        message_id = event.metadata.get(
                            "message_id", str(uuid.uuid4())
                        )
                    yield {"message_id": message_id, "content": event.content}

                elif event.type == "continuation":
                    logger.info(
                        "Agent loop continuation #%d",
                        event.metadata.get("iteration", 0),
                    )

                elif event.type == "validation_retry":
                    logger.info(
                        "Agent loop validation retry #%d",
                        event.metadata.get("retry", 0),
                    )

                elif event.type == "budget_warning":
                    logger.warning(
                        "Agent loop budget: %s/%s tokens",
                        event.metadata.get("total_tokens"),
                        event.metadata.get("budget"),
                    )

                elif event.type == "error":
                    logger.error("Agent loop error: %s", event.content)

                elif event.type == "complete":
                    metrics = event.metadata.get("metrics", {})
                    if message_id is None:
                        message_id = event.metadata.get(
                            "message_id", str(uuid.uuid4())
                        )
                    logger.info(
                        "Agent loop complete: %d iters, %dms, by=%s",
                        metrics.get("iterations", 0),
                        metrics.get("elapsed_ms", 0),
                        event.metadata.get("terminated_by", "unknown"),
                    )
                    yield {
                        "event": "complete_metrics",
                        "metrics": metrics,
                    }

    async def _build_loop_config(self, todo_id: uuid.UUID):
        from arc.application.execution.agent_loop import LoopConfig
        from arc.infrastructure.repositories.project import ProjectRepository
        from arc.infrastructure.repositories.todo import TodoRepository

        todo_repo = TodoRepository(self._db)
        todo = await todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return LoopConfig()

        project = await ProjectRepository(self._db).get_by_id(todo.project_id)
        if not project or not project.conversation_config:
            return LoopConfig()

        loop_cfg = project.conversation_config.get("loop_config", {})
        return LoopConfig(
            token_budget=loop_cfg.get("token_budget", 120000),
            wall_timeout_seconds=loop_cfg.get("wall_timeout_seconds", 300.0),
            max_tokens_per_call=loop_cfg.get("max_tokens_per_call", 16384),
        )

    async def _extract_experience(self, todo_id: uuid.UUID) -> None:
        from arc.application.experience.service import ExperienceService
        from arc.infrastructure.repositories.todo import TodoRepository

        try:
            todo_repo = TodoRepository(self._db)
            todo = await todo_repo.get_by_id(todo_id)
            if not todo:
                return
            svc = ExperienceService(self._db)
            await svc.extract_from_todo(todo)
        except Exception as exc:
            logger.warning(
                "Experience extraction failed for todo %s: %s", todo_id, exc
            )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _needs_user_input(content: str) -> bool:
    """检测 AI 输出是否需要用户确认/澄清。"""
    if "[NEEDS_INPUT]" in content:
        return True
    last_paragraph = content.strip().split("\n\n")[-1] if content.strip() else ""
    question_indicators = ["？", "?", "你觉得", "你希望", "请确认", "你选择", "你倾向"]
    return any(ind in last_paragraph for ind in question_indicators)


def _map_tool_event(event) -> list[dict]:
    """将 ToolLoopEvent 映射为前端 SSE 字典。"""
    results = []
    mid = event.metadata.get("message_id", str(uuid.uuid4()))

    if event.type == "text_delta":
        results.append({"message_id": mid, "content": event.content})
    elif event.type == "tool_call":
        results.append({
            "message_id": mid,
            "event": "tool_call",
            "tool_name": event.content,
            "tool_input": event.metadata.get("input", {}),
            "round": event.metadata.get("round", 0),
            "parallel": event.metadata.get("parallel", False),
        })
    elif event.type == "tool_result":
        results.append({
            "message_id": mid,
            "event": "tool_result",
            "tool_name": event.metadata.get("tool_name", ""),
            "output_preview": event.content,
            "is_error": event.metadata.get("is_error", False),
            "parallel": event.metadata.get("parallel", False),
        })
    elif event.type in ("orchestration_start", "synthesis_start", "orchestration_complete"):
        results.append({"event": event.type, **event.metadata})
    elif event.type in ("worker_start", "worker_complete", "worker_error"):
        results.append({"event": event.type, **event.metadata})
    elif event.type == "approval_required":
        results.append({"event": "approval_required", **event.metadata})
    elif event.type == "error":
        logger.error("Tool loop error: %s", event.content)
    elif event.type == "complete":
        logger.info(
            "Tool loop complete: %d rounds, %d tokens, %dms",
            event.metadata.get("tool_rounds", 0),
            event.metadata.get("total_tokens", 0),
            event.metadata.get("elapsed_ms", 0),
        )
        results.append({
            "event": "complete_metrics",
            "metrics": {
                "tool_rounds": event.metadata.get("tool_rounds", 0),
                "total_tokens": event.metadata.get("total_tokens", 0),
                "elapsed_ms": event.metadata.get("elapsed_ms", 0),
            },
        })
    return results
