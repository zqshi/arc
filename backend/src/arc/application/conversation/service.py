"""Pipeline 模式对话服务。

职责:读取项目执行配置(project_path / sandbox_policy / orchestration / llm_config),
委托 ExecutionEngine 完成流式执行(工具循环 / 沙箱隔离 / 多 worker 编排 / artifact 抽取)。

与 application/execution/conversation_strategy.py 的 ConversationExecutionService(unified 模式)
委托同一 ExecutionEngine,prompt 构建统一走 PromptBuilder → ContextAssembler。
"""

from __future__ import annotations

import logging
import uuid
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.context.prompt_builder import PromptBuilder
from arc.application.execution.artifact_extractor import ArtifactExtractor
from arc.application.execution.execution_engine import ExecutionEngine
from arc.domain.conversation.entity import Conversation, Message
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.planning import DeliverableTrackerRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conv_repo = ConversationRepository(db)
        self.todo_repo = TodoRepository(db)
        self.artifact_repo = ArtifactRepository(db)
        self.tracker_repo = DeliverableTrackerRepository(db)
        self.extractor = ArtifactExtractor(db)
        self._prompt_builder = PromptBuilder(db)
        self._engine = ExecutionEngine(
            db, self._prompt_builder, self.conv_repo, self.tracker_repo, self.extractor,
        )

    async def generate_response(self, conversation: Conversation) -> Message:
        """非流式回复 — 消费 ExecutionEngine 事件流,返回写入的最后 assistant 消息。

        ExecutionEngine 内部已完成 add_message + 持久化 + artifact 抽取,
        调用方不应再次持久化该消息。
        """
        async for _ in self._generate(conversation):
            pass
        return conversation.messages[-1]

    async def generate_response_stream(
        self, conversation: Conversation,
    ) -> AsyncIterator[dict]:
        """生成 AI 流式回复。委托给 ExecutionEngine。"""
        async for chunk in self._generate(conversation):
            yield chunk

    async def _generate(self, conversation: Conversation) -> AsyncIterator[dict]:
        """读取项目执行配置并委托 ExecutionEngine。"""
        project_path = await self._get_project_local_path(conversation.todo_id)
        sandbox_policy = await self._get_sandbox_policy(conversation.todo_id)
        orchestration_enabled = await self._is_orchestration_enabled(conversation.todo_id)
        llm_config = await self._get_llm_config(conversation.todo_id)

        async for chunk in self._engine.generate_response_stream(
            conversation,
            project_path=project_path,
            sandbox_policy=sandbox_policy,
            orchestration_enabled=orchestration_enabled,
            llm_config=llm_config,
        ):
            yield chunk

    # ------------------------------------------------------------------
    # Project execution config — 读取项目级配置供 ExecutionEngine 使用
    # ------------------------------------------------------------------

    async def _get_project_local_path(self, todo_id: uuid.UUID) -> str | None:
        """获取项目本地路径 — 有路径时启用 ToolAwareLoop。"""
        from pathlib import Path

        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.local_path:
            return None
        resolved = Path(project.local_path).expanduser().resolve()
        if resolved.is_dir():
            return str(resolved)
        return None

    async def _get_sandbox_policy(self, todo_id: uuid.UUID):
        """构造 sandbox 策略 — 策略解析逻辑见 sandbox.policy_resolver。"""
        from arc.application.sandbox.policy_resolver import resolve_sandbox_policy
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project:
            return None
        return resolve_sandbox_policy(project)

    async def _is_orchestration_enabled(self, todo_id: uuid.UUID) -> bool:
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return False
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project or not project.conversation_config:
            return False
        orch_cfg = project.conversation_config.get("orchestration", {})
        return bool(orch_cfg.get("enabled", False))

    async def _get_llm_config(self, todo_id: uuid.UUID) -> dict | None:
        """获取项目级 LLM 配置 (v6.21 D3: 补 llm_provider_id, 统一走 LLMProviderService)。

        修复 v6.20 L5 遗漏: pipeline 路径原只读 conversation_config["llm"] 明文,
        跳过 llm_provider_id。现对齐 unified 路径 (conversation_context.get_llm_config),
        优先级链一致 (项目 llm_provider_id → 旧明文 → 用户默认 → None)。
        """
        from arc.application.llm.service import LLMProviderService
        from arc.infrastructure.repositories.project import ProjectRepository

        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return None
        project = await ProjectRepository(self.db).get_by_id(todo.project_id)
        if not project:
            return None
        return await LLMProviderService(self.db).resolve_from_project(
            project, project.user_id
        )
