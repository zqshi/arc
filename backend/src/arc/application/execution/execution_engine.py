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

from arc.application.execution.autopilot import AutopilotMixin
from arc.application.execution.execution_helpers import (
    build_loop_config as _build_loop_config,
)
from arc.application.execution.execution_helpers import (
    extract_experience as _extract_experience,
)
from arc.application.execution.execution_helpers import (
    map_agent_loop_events as _map_agent_loop_events,
)
from arc.application.execution.execution_helpers import (
    map_tool_event as _map_tool_event,
)
from arc.application.execution.execution_helpers import (
    summarize_tool_input as _summarize_tool_input,
)
from arc.application.execution.execution_helpers import (
    trigger_pre_llm_hooks as _trigger_pre_llm_hooks,
)
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


class ExecutionEngine(AutopilotMixin):
    """编排 LLM 流式执行，支持 tool-use / text-only / 多 Agent 三种路径。

    集成:
    - HookManager (Harness §12) — 7 注入点的扩展管道
    - CheckpointManager (Harness §11) — autopilot 里程碑快照 (run_autopilot 在 AutopilotMixin)
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
        llm_config: dict | None = None,
    ) -> AsyncIterator[dict]:
        """生成 AI 流式回复。"""
        await _trigger_pre_llm_hooks(
            self._hooks, str(conversation.id), len(conversation.messages), project_path,
        )

        llm_messages = await self._prompt_builder.build_llm_messages(conversation)

        message_id: str | None = None
        full_content = ""
        loop_metrics: dict = {}
        tool_calls_log: list[dict] = []  # 收集工具调用记录

        if project_path:
            async for event_dict in self._tool_aware_stream(
                llm_messages, project_path, sandbox_policy, orchestration_enabled,
                llm_config=llm_config,
                conversation_id=str(conversation.id),
                todo_id=conversation.todo_id,
            ):
                if "message_id" in event_dict and event_dict.get("content"):
                    if message_id is None:
                        message_id = event_dict["message_id"]
                    full_content += event_dict["content"]
                if event_dict.get("event") == "complete_metrics":
                    loop_metrics = event_dict.get("metrics", {})
                    continue
                # 收集工具调用记录用于持久化
                if event_dict.get("event") == "tool_call":
                    tool_calls_log.append({
                        "tool_name": event_dict.get("tool_name", ""),
                        "tool_input_summary": _summarize_tool_input(
                            event_dict.get("tool_name", ""),
                            event_dict.get("tool_input", {}),
                        ),
                    })
                elif event_dict.get("event") == "tool_result":
                    if tool_calls_log:
                        tool_calls_log[-1]["is_error"] = event_dict.get("is_error", False)
                        tool_calls_log[-1]["output_preview"] = event_dict.get(
                            "output_preview", ""
                        )[:200]
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
                "tool_calls": tool_calls_log[:50] if tool_calls_log else [],
                "referenced_experiences": [
                    {"id": str(eid)}
                    for eid in self._prompt_builder.injected_experience_ids
                ],
            },
            id=uuid.UUID(message_id),
        )
        await self._conv_repo.add_message(conversation.id, ai_message)

        extracted = await self._extractor.process_message(
            full_content, conversation.todo_id,
        )
        if extracted:
            # 先 commit 确保前端 fetchTracker 能读到最新 tracker 状态
            await self._db.commit()
            artifact_names = [
                ARTIFACT_LABELS.get(a.artifact_type, a.artifact_type.value)
                for a in extracted
            ]
            # 读取最新 tracker 快照，随事件一起推送给前端（避免额外 API 往返）
            tracker = await self._tracker_repo.get_by_todo_id(conversation.todo_id)
            tracker_snapshot = None
            if tracker:
                tracker_snapshot = {
                    "required": tracker.required,
                    "deliverables": {k: v.value for k, v in tracker.deliverables.items()},
                    "completion_pct": tracker.completion_pct,
                    "is_complete": tracker.is_complete,
                }
            yield {
                "message_id": message_id,
                "event": "artifacts_extracted",
                "artifacts": [str(a.id) for a in extracted],
                "artifact_names": artifact_names,
                "tracker": tracker_snapshot,
            }
            if tracker and tracker.is_complete:
                await _extract_experience(self._db, conversation.todo_id, self._prompt_builder)

    # ------------------------------------------------------------------
    # Tool-aware execution path
    # ------------------------------------------------------------------

    async def _tool_aware_stream(
        self,
        llm_messages: list,
        project_path: str,
        sandbox_policy,
        orchestration_enabled: bool,
        llm_config: dict | None = None,
        *,
        conversation_id: str = "",
        todo_id: uuid.UUID | None = None,
    ) -> AsyncIterator[dict]:
        from arc.application.ai.adapter_pool import adapter_pool
        from arc.application.context.compression import CompressionManager
        from arc.application.execution.drift_detector import DriftDetector
        from arc.application.execution.error_loop_detector import ErrorLoopDetector
        from arc.application.execution.llm_review import default_llm_review
        from arc.application.execution.tool_loop import ToolAwareLoop
        from arc.application.execution.tools import ToolRegistry

        registry = ToolRegistry(project_path)
        compression = CompressionManager()  # L1 不需要 LLM adapter

        # 从 llm_messages 提取用户目标用于漂移检测
        user_goal = ""
        for m in reversed(llm_messages):
            if m.role == "user":
                user_goal = m.content[:500]
                break

        drift_detector = (
            DriftDetector(user_goal, llm_review_fn=default_llm_review)
            if user_goal
            else None
        )
        error_detector = ErrorLoopDetector(llm_review_fn=default_llm_review)

        # Sandbox integration — conditional import (no circular dep; deferred
        # purely to avoid loading sandbox modules when sandbox is disabled)
        sandbox_runtime = None
        if sandbox_policy and sandbox_policy.mode.value != "none":
            from arc.application.execution.stream_manager import stream_manager
            from arc.application.execution.tools import _run_command, _write_file
            from arc.application.sandbox.runtime import create_sandbox_runtime
            from arc.application.sandbox.tools import SandboxedToolRegistry

            # v6.7: emit_callback 经 stream_manager 把审批事件发到 conversation 流,
            # 避免 application 层直接依赖 interface (DDD)。runtime 内部监听
            # bus arc:sandbox:{cid} 接收审批响应 (跨 worker 路由)。
            async def _emit_approval(event: dict) -> None:
                await stream_manager.publish_event(conversation_id, event)

            sandbox_runtime = create_sandbox_runtime(
                sandbox_policy, project_path,
                conversation_id=conversation_id,
                emit_callback=_emit_approval,
                run_command_impl=_run_command,
                write_file_impl=_write_file,
            )
            registry = SandboxedToolRegistry(project_path, sandbox_runtime)

        # CI target 注册 build 工具 (T3-g 设计2; docker target 不注册, 用 run_command)
        build_target = sandbox_policy.target if sandbox_policy else None
        if build_target is not None and todo_id is not None:
            registry.register_build_tool(
                build_target=build_target,
                todo_id=todo_id,
                db=self._db,
                conversation_id=conversation_id,
                local_dir=project_path,
            )

        # Orchestration or single-agent
        try:
            if orchestration_enabled:
                from arc.application.orchestration.service import OrchestrationService

                orch = OrchestrationService(adapter_pool)
                event_stream = orch.execute(llm_messages, registry)
            else:
                async def _single():
                    async with adapter_pool.acquire_for_project(llm_config) as adapter:
                        loop = ToolAwareLoop(
                            adapter, registry,
                            compression=compression,
                            drift_detector=drift_detector,
                            error_loop_detector=error_detector,
                            llm_review_fn=default_llm_review,
                        )
                        async for ev in loop.run(llm_messages):
                            yield ev
                event_stream = _single()

            async for event in event_stream:
                for mapped in _map_tool_event(event):
                    yield mapped
        finally:
            # v6.7: stream 结束释放沙箱资源 (OpenSandbox kill); 长驻缓存记入技术债务
            if sandbox_runtime is not None:
                try:
                    await sandbox_runtime.close()
                except Exception as exc:
                    logger.warning("Sandbox close failed: %s", exc)

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
        )

        validator = DeliverableValidator(DELIVERABLE_REQUIRED_FIELDS)
        config = await _build_loop_config(self._db, todo_id)

        async with adapter_pool.acquire() as adapter:
            loop = AgentLoop(adapter, config)
            async for mapped in _map_agent_loop_events(loop.run(llm_messages, validator=validator)):
                yield mapped
