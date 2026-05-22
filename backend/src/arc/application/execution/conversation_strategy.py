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
    CONVERSATION_MODE_SYSTEM_PROMPT,
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
        """生成AI流式回复，完成后自动提取产出物。"""
        from arc.application.ai.adapter_pool import adapter_pool

        llm_messages = await self._build_llm_messages(conversation)

        async with adapter_pool.acquire() as adapter:
            message_id = str(uuid.uuid4())
            full_content = ""

            async for chunk in adapter.chat_stream(llm_messages):
                full_content += chunk
                yield {"message_id": message_id, "content": chunk}

        ai_message = conversation.add_message(
            role=MessageRole.ASSISTANT,
            content=full_content,
            metadata={"message_id": message_id, "streamed": True, "mode": "conversation"},
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

    async def get_tracker_state(self, todo_id: uuid.UUID) -> dict:
        """获取交付物追踪器状态。"""
        tracker = await self.tracker_repo.get_by_todo_id(todo_id)
        if not tracker:
            return {"required": [], "deliverables": {}, "completion_pct": 0}

        return {
            "required": tracker.required,
            "deliverables": {k: v.value for k, v in tracker.deliverables.items()},
            "completion_pct": tracker.completion_pct,
            "is_complete": tracker.is_complete,
        }

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
        completed_artifacts_text = "暂无"

        if todo and todo.project_id:
            from arc.application.context.provider import ProjectContextProvider

            ctx_provider = ProjectContextProvider(self.db)
            project_ctx = await ctx_provider.get_context(conversation.todo_id)
            project_context = project_ctx.to_prompt_section()

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

        return CONVERSATION_MODE_SYSTEM_PROMPT.format(
            title=todo.title if todo else "",
            description=todo.description if todo else "",
            deliverable_section=deliverable_section,
            project_context=project_context,
            experience_context=experience_context,
            completed_artifacts=completed_artifacts_text,
        )

    async def _create_tracker(
        self,
        todo_id: uuid.UUID,
        required_types: list[str] | None,
    ) -> DeliverableTracker:
        if not required_types:
            from arc.domain.project.value_objects import DEFAULT_CONVERSATION_CONFIG

            required_types = DEFAULT_CONVERSATION_CONFIG["required_deliverables"]

        return await self.extractor.get_or_create_tracker(todo_id, required_types)
