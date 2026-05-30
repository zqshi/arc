"""对话驱动执行模式的核心服务。

与Pipeline模式不同，对话模式：
- 一个Todo只有一个统一对话（purpose=unified）
- AI根据对话进展自动判断阶段并产出交付物
- 交付物通过 [DELIVERABLE:type] 标记从AI输出中自动提取
- DeliverableTracker追踪完成进度
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.execution.artifact_extractor import ArtifactExtractor
from arc.application.execution.prompts import (
    ARTIFACT_SCHEMAS,
    AUTOPILOT_SECTION,
    CONVERSATION_MODE_SYSTEM_PROMPT,
    build_ddd_tdd_section,
    build_deliverable_checklist,
)
from arc.domain.artifact.value_objects import ARTIFACT_LABELS, ArtifactType
from arc.domain.conversation.entity import Conversation
from arc.domain.planning.entity import DeliverableTracker
from arc.domain.todo.value_objects import ConversationPurpose, MessageRole, TodoStatus
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.planning import DeliverableTrackerRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


class ConversationExecutionService:
    """对话驱动模式的执行引擎。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.todo_repo = TodoRepository(db)
        self.conv_repo = ConversationRepository(db)
        self.artifact_repo = ArtifactRepository(db)
        self.tracker_repo = DeliverableTrackerRepository(db)
        self.extractor = ArtifactExtractor(db)

    async def initialize(
        self,
        todo_id: uuid.UUID,
        required_deliverables: list[str] | None = None,
    ) -> tuple[Conversation, DeliverableTracker]:
        """初始化对话模式：创建统一对话 + 交付物追踪器。"""
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo:
            raise ValueError(f"Todo {todo_id} not found")

        existing_conv = await self.conv_repo.get_by_todo_and_purpose(
            todo_id,
            ConversationPurpose.UNIFIED,
        )
        if existing_conv:
            if todo.status == TodoStatus.PENDING:
                todo.start_conversation()
                await self.todo_repo.update(todo)
            tracker = await self.tracker_repo.get_by_todo_id(todo_id)
            if not tracker:
                tracker = await self._create_tracker(todo_id, required_deliverables)
            else:
                tracker = await self._sync_tracker_required(
                    tracker, todo, required_deliverables
                )
            return existing_conv, tracker

        conv = Conversation(
            todo_id=todo_id,
            purpose=ConversationPurpose.UNIFIED,
        )
        conv.add_message(
            role=MessageRole.SYSTEM,
            content=f"对话模式启动：{todo.title}",
        )
        greeting = (
            f"你好！我来帮你完成「{todo.title}」。\n\n"
            f"在对话过程中，我会根据我们的讨论自动产出结构化交付物。"
            f"你可以随时在侧边面板查看进度。\n\n"
        )
        if todo.description:
            greeting += f"我看到你的描述是：{todo.description}\n\n"
            greeting += "先聊聊这个需求要解决什么问题？有哪些关键的用户场景？"
        else:
            greeting += "先描述一下你想做什么？解决什么问题？"

        conv.add_message(role=MessageRole.ASSISTANT, content=greeting)
        await self.conv_repo.create(conv)

        if todo.status == TodoStatus.PENDING:
            todo.start_conversation()
            await self.todo_repo.update(todo)

        tracker = await self._create_tracker(todo_id, required_deliverables)
        return conv, tracker

    async def generate_response_stream(
        self,
        conversation: Conversation,
    ) -> AsyncIterator[dict]:
        """生成AI流式回复。当项目有 local_path 时启用 Tool Use。"""
        from arc.application.ai.adapter_pool import adapter_pool

        llm_messages = await self._build_llm_messages(conversation)
        project_path = await self._get_project_local_path(conversation.todo_id)

        # Tool-aware path: project has local code directory
        if project_path:
            from arc.application.execution.tool_loop import ToolAwareLoop, ToolLoopEvent
            from arc.application.execution.tools import ToolRegistry

            registry = ToolRegistry(project_path)
            message_id = None
            full_content = ""

            async with adapter_pool.acquire() as adapter:
                loop = ToolAwareLoop(adapter, registry)
                async for event in loop.run(llm_messages):
                    if event.type == "text_delta":
                        if message_id is None:
                            message_id = event.metadata.get("message_id", str(uuid.uuid4()))
                        full_content += event.content
                        yield {"message_id": message_id, "content": event.content}

                    elif event.type == "tool_call":
                        yield {
                            "message_id": message_id or str(uuid.uuid4()),
                            "event": "tool_call",
                            "tool_name": event.content,
                            "tool_input": event.metadata.get("input", {}),
                            "round": event.metadata.get("round", 0),
                        }

                    elif event.type == "tool_result":
                        yield {
                            "message_id": message_id or str(uuid.uuid4()),
                            "event": "tool_result",
                            "tool_name": event.metadata.get("tool_name", ""),
                            "output_preview": event.content,
                            "is_error": event.metadata.get("is_error", False),
                        }

                    elif event.type == "error":
                        logger.error("Tool loop error: %s", event.content)

                    elif event.type == "complete":
                        if message_id is None:
                            message_id = event.metadata.get("message_id", str(uuid.uuid4()))
                        logger.info(
                            "Tool loop complete: %d rounds, %d tokens, %dms",
                            event.metadata.get("tool_rounds", 0),
                            event.metadata.get("total_tokens", 0),
                            event.metadata.get("elapsed_ms", 0),
                        )

        else:
            # Original text-only path
            from arc.application.execution.agent_loop import (
                DELIVERABLE_REQUIRED_FIELDS,
                AgentLoop,
                DeliverableValidator,
                LoopConfig,
            )

            validator = DeliverableValidator(DELIVERABLE_REQUIRED_FIELDS)
            config = await self._build_loop_config(conversation.todo_id)

            message_id = None
            full_content = ""

            async with adapter_pool.acquire() as adapter:
                loop = AgentLoop(adapter, config)
                async for event in loop.run(llm_messages, validator=validator):
                    if event.type == "chunk":
                        if message_id is None:
                            message_id = event.metadata.get("message_id", str(uuid.uuid4()))
                        full_content += event.content
                        yield {"message_id": message_id, "content": event.content}

                    elif event.type == "continuation":
                        logger.info(
                            "Agent loop continuation #%d (transparent)",
                            event.metadata.get("iteration", 0),
                        )

                    elif event.type == "validation_retry":
                        logger.info(
                            "Agent loop validation retry #%d",
                            event.metadata.get("retry", 0),
                        )

                    elif event.type == "budget_warning":
                        logger.warning(
                            "Agent loop budget exceeded: %s/%s tokens",
                            event.metadata.get("total_tokens"),
                            event.metadata.get("budget"),
                        )

                    elif event.type == "error":
                        logger.error("Agent loop error: %s", event.content)

                    elif event.type == "complete":
                        full_content = event.content
                        metrics = event.metadata.get("metrics", {})
                        if message_id is None:
                            message_id = event.metadata.get("message_id", str(uuid.uuid4()))
                        logger.info(
                            "Agent loop complete: %d iters, %d conts, %dms, by=%s",
                            metrics.get("iterations", 0),
                            metrics.get("continuations", 0),
                            metrics.get("elapsed_ms", 0),
                            event.metadata.get("terminated_by", "unknown"),
                        )

        if not message_id:
            message_id = str(uuid.uuid4())

        ai_message = conversation.add_message(
            role=MessageRole.ASSISTANT,
            content=full_content,
            metadata={
                "message_id": message_id,
                "streamed": True,
                "mode": "conversation",
                "agent_loop": loop.metrics.__dict__,
            },
        )
        await self.conv_repo.add_message(conversation.id, ai_message)

        extracted = await self.extractor.process_message(
            full_content,
            conversation.todo_id,
        )
        if extracted:
            artifact_names = [
                ARTIFACT_LABELS.get(a.artifact_type, a.artifact_type.value) for a in extracted
            ]
            yield {
                "message_id": message_id,
                "event": "artifacts_extracted",
                "artifacts": [str(a.id) for a in extracted],
                "artifact_names": artifact_names,
            }
            tracker = await self.tracker_repo.get_by_todo_id(conversation.todo_id)
            if tracker and tracker.is_complete:
                await self._extract_experience(conversation.todo_id)

    async def run_autopilot(
        self,
        conversation: Conversation,
    ) -> AsyncIterator[dict]:
        """自驾模式：持续生成直到任务完成或需要用户澄清。"""
        max_rounds = 12

        for round_num in range(max_rounds):
            async for chunk in self.generate_response_stream(conversation):
                yield chunk

            tracker = await self.tracker_repo.get_by_todo_id(conversation.todo_id)
            if tracker and tracker.is_complete:
                await self._extract_experience(conversation.todo_id)
                yield {"event": "autopilot_complete", "reason": "all_deliverables_done"}
                return

            last_msg = conversation.messages[-1] if conversation.messages else None
            if last_msg and self._needs_user_input(last_msg.content):
                yield {"event": "autopilot_paused", "reason": "needs_user_input"}
                return

            advance_msg = conversation.add_message(
                role=MessageRole.USER,
                content="继续推进下一个阶段。",
                metadata={"auto_advance": True, "round": round_num + 1},
            )
            await self.conv_repo.add_message(conversation.id, advance_msg)

        yield {"event": "autopilot_paused", "reason": "max_rounds_reached"}

    async def get_autonomy(self, todo_id: uuid.UUID) -> str:
        """获取当前 todo 所属项目的 agent_autonomy 配置。"""
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return "supervised"
        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.conversation_config:
            return "supervised"
        return project.conversation_config.get("agent_autonomy", "supervised")

    async def _get_project_local_path(self, todo_id: uuid.UUID) -> str | None:
        """获取项目 local_path，验证目录存在后返回。"""
        from pathlib import Path

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.local_path:
            return None
        resolved = Path(project.local_path).expanduser().resolve()
        if resolved.is_dir():
            return str(resolved)
        logger.warning("Project local_path does not exist: %s", project.local_path)
        return None

    @staticmethod
    def _needs_user_input(content: str) -> bool:
        """检测 AI 输出是否需要用户确认/澄清。"""
        if "[NEEDS_INPUT]" in content:
            return True
        last_paragraph = content.strip().split("\n\n")[-1] if content.strip() else ""
        question_indicators = ["？", "?", "你觉得", "你希望", "请确认", "你选择", "你倾向"]
        return any(ind in last_paragraph for ind in question_indicators)

    async def get_tracker_state(self, todo_id: uuid.UUID) -> dict:
        """获取交付物追踪器状态，自动同步最新 required 列表并修复不一致。"""
        tracker = await self.tracker_repo.get_by_todo_id(todo_id)
        if not tracker:
            return {"required": [], "deliverables": {}, "completion_pct": 0}

        todo = await self.todo_repo.get_by_id(todo_id)
        tracker = await self._sync_tracker_required(tracker, todo, None)

        from arc.domain.planning.value_objects import DeliverableStatus

        artifacts = await self.artifact_repo.list_by_todo_id(todo_id)
        produced_types = {a.artifact_type.value for a in artifacts}
        reconciled = False
        for atype in produced_types:
            status = tracker.deliverables.get(atype)
            if status and status not in (DeliverableStatus.PRODUCED, DeliverableStatus.CONFIRMED):
                tracker.deliverables[atype] = DeliverableStatus.PRODUCED
                reconciled = True
        if reconciled:
            await self.tracker_repo.update(tracker)
            await self.db.commit()

        return {
            "required": tracker.required,
            "deliverables": {k: v.value for k, v in tracker.deliverables.items()},
            "completion_pct": tracker.completion_pct,
            "is_complete": tracker.is_complete,
        }

    async def _build_loop_config(self, todo_id: uuid.UUID):
        """从项目 conversation_config 构建 LoopConfig。"""
        from arc.application.execution.agent_loop import LoopConfig

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return LoopConfig()

        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.conversation_config:
            return LoopConfig()

        loop_cfg = project.conversation_config.get("loop_config", {})
        return LoopConfig(
            token_budget=loop_cfg.get("token_budget", 120000),
            wall_timeout_seconds=loop_cfg.get("wall_timeout_seconds", 300.0),
            max_tokens_per_call=loop_cfg.get("max_tokens_per_call", 16384),
        )

    async def _build_llm_messages(self, conversation: Conversation) -> list:
        from arc.application.ai.llm_adapter import LLMMessage

        messages = []
        todo = await self.todo_repo.get_by_id(conversation.todo_id)

        system_prompt = await self._build_system_prompt(conversation, todo)
        messages.append(LLMMessage(role="system", content=system_prompt))

        for msg in conversation.get_context_window(max_messages=50):
            messages.append(LLMMessage(role=msg.role.value, content=msg.content))

        return messages

    async def _build_system_prompt(self, conversation: Conversation, todo) -> str:
        tracker = await self.tracker_repo.get_by_todo_id(conversation.todo_id)
        required = tracker.required if tracker else []
        completed = [
            k
            for k, v in (tracker.deliverables if tracker else {}).items()
            if v.value in ("produced", "confirmed")
        ]

        checklist = build_deliverable_checklist(required, completed)
        deliverable_section = f"""## 交付物清单（渐进式完成）
{checklist}

## 交付物输出规则
当你认为某个交付物内容已经充分时，使用以下格式输出：

[DELIVERABLE:artifact_type]
```json
(结构化内容)
```

可用的artifact_type及其schema：
""" + "\n".join(
            f"- **{ARTIFACT_LABELS.get(ArtifactType(t), t)}** (`{t}`):"
            f"\n```\n{ARTIFACT_SCHEMAS.get(t, '{}')}\n```"
            for t in required
            if t not in completed
        )

        project_context = ""
        experience_context = ""
        ddd_tdd_context = ""
        completed_artifacts_text = "暂无"

        if todo and todo.project_id:
            from arc.application.context.provider import ProjectContextProvider
            from arc.infrastructure.repositories.project import ProjectRepository

            ctx_provider = ProjectContextProvider(self.db)
            project_ctx = await ctx_provider.get_context(conversation.todo_id)
            project_context = project_ctx.to_prompt_section()

            project = await ProjectRepository(self.db).get_by_id(todo.project_id)
            if project and project.domain_model:
                ddd_tdd_context = build_ddd_tdd_section(project.domain_model)

        if completed:
            artifacts = await self.artifact_repo.list_by_todo_id(conversation.todo_id)
            parts = []
            for a in artifacts:
                if a.artifact_type.value in completed:
                    label = ARTIFACT_LABELS.get(a.artifact_type, a.artifact_type.value)
                    content_summary = json.dumps(a.content, ensure_ascii=False, indent=2)
                    if len(content_summary) > 500:
                        content_summary = content_summary[:500] + "..."
                    parts.append(f"### {label}\n{content_summary}")
            if parts:
                completed_artifacts_text = "\n\n".join(parts)

        if todo:
            from arc.application.conversation.service import ConversationService

            conv_svc = ConversationService(self.db)
            try:
                exp_text, _ = await conv_svc._build_experience_context(todo, None)
                if exp_text:
                    experience_context = f"## 相关历史经验\n{exp_text}"
            except Exception:
                pass

        if ddd_tdd_context:
            project_context = project_context + "\n\n" + ddd_tdd_context

        # Inject code operation capability description when tools are available
        code_capability = ""
        if todo and todo.project_id:
            local_path = await self._get_project_local_path(conversation.todo_id)
            if local_path:
                code_capability = f"""

## 代码操作能力（重要）
你可以直接操作项目代码。项目工作目录: `{local_path}`

可用工具：
- `list_directory` — 查看目录结构，了解项目全貌
- `read_file` — 阅读源码文件，支持指定行范围
- `grep_search` — 搜索代码中的文本/模式
- `run_command` — 执行 shell 命令（git/npm/pytest/ls 等）
- `write_file` — 创建或修改文件

需要了解代码时直接用工具读取，不要让用户贴代码。"""

        autonomy = await self.get_autonomy(conversation.todo_id)
        autopilot_section = AUTOPILOT_SECTION if autonomy == "full" else ""

        return CONVERSATION_MODE_SYSTEM_PROMPT.format(
            title=todo.title if todo else "",
            description=todo.description if todo else "",
            deliverable_section=deliverable_section,
            project_context=(
                project_context + code_capability + ("\n\n" + autopilot_section if autopilot_section else "")
            ),
            experience_context=experience_context,
            completed_artifacts=completed_artifacts_text,
        )

    async def _create_tracker(
        self,
        todo_id: uuid.UUID,
        required_types: list[str] | None,
    ) -> DeliverableTracker:
        if not required_types:
            todo = await self.todo_repo.get_by_id(todo_id)
            if todo and todo.project_id:
                from arc.infrastructure.repositories.project import ProjectRepository

                project = await ProjectRepository(self.db).get_by_id(todo.project_id)
                if project and project.conversation_config:
                    required_types = project.conversation_config.get("required_deliverables")

        if not required_types:
            from arc.domain.project.value_objects import DEFAULT_CONVERSATION_CONFIG

            required_types = DEFAULT_CONVERSATION_CONFIG["required_deliverables"]

        return await self.extractor.get_or_create_tracker(todo_id, required_types)

    async def _sync_tracker_required(
        self,
        tracker: DeliverableTracker,
        todo,
        override: list[str] | None,
    ) -> DeliverableTracker:
        """Ensure tracker.required matches the current canonical list.

        Adds missing types and reorders to match canonical sequence.
        """
        canonical = override
        if not canonical:
            if todo and todo.project_id:
                from arc.infrastructure.repositories.project import ProjectRepository

                project = await ProjectRepository(self.db).get_by_id(
                    todo.project_id
                )
                if project and project.conversation_config:
                    canonical = project.conversation_config.get(
                        "required_deliverables"
                    )
        if not canonical:
            from arc.domain.project.value_objects import DEFAULT_CONVERSATION_CONFIG

            canonical = DEFAULT_CONVERSATION_CONFIG["required_deliverables"]

        from arc.domain.planning.value_objects import DeliverableStatus

        existing = set(tracker.required)
        added = [t for t in canonical if t not in existing]
        needs_reorder = tracker.required != [
            t for t in canonical if t in existing
        ] + added

        if not added and not needs_reorder:
            return tracker

        for t in added:
            if t not in tracker.deliverables:
                tracker.deliverables[t] = DeliverableStatus.PENDING

        tracker.required = list(canonical)

        await self.tracker_repo.update(tracker)
        logger.info(
            "Synced tracker %s: added deliverables %s",
            tracker.id,
            added,
        )
        return tracker

    async def _extract_experience(self, todo_id: uuid.UUID) -> None:
        from arc.application.experience.service import ExperienceService

        try:
            todo = await self.todo_repo.get_by_id(todo_id)
            if not todo:
                return
            svc = ExperienceService(self.db)
            await svc.extract_from_todo(todo)
        except Exception as exc:
            logger.warning("Experience extraction failed for todo %s: %s", todo_id, exc)
