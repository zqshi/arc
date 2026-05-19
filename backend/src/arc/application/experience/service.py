from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.ai.json_extract import extract_json
from arc.domain.experience.entity import Experience
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import ExperienceScope, ExperienceStatus, Tag
from arc.infrastructure.repositories.conversation import ConversationRepository
from arc.infrastructure.repositories.experience import ExperienceRepository

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT = """你是一个经验提取专家。根据以下待办任务的完整信息和对话记录，提取一条结构化经验。

## 任务信息
标题: {title}
描述: {description}
背景: {background}
目标: {goals}
技术方案: {tech_plan}

## 对话记录
{conversation_log}

请以JSON格式输出：
{{
  "title": "经验标题（简洁概括）",
  "problem": "遇到的问题",
  "solution": "解决方案",
  "decisions": ["关键决策1", "关键决策2"],
  "pitfalls": ["踩坑点1", "踩坑点2"],
  "applicable_scenarios": "适用场景描述",
  "tags": ["标签1", "标签2"]
}}

只输出JSON，不要其他内容。"""


TAG_COLORS = {
    "认证": "#4A9FD8", "安全": "#EF4444", "性能": "#E5A93D",
    "前端": "#34D399", "后端": "#4A9FD8", "数据库": "#A78BFA",
    "架构": "#F59E0B", "支付": "#A78BFA", "第三方": "#F59E0B",
    "导出": "#4A9FD8", "缓存": "#E5A93D", "API": "#34D399",
}


class ExperienceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.exp_repo = ExperienceRepository(db)
        self.conv_repo = ConversationRepository(db)

    async def extract_from_todo(self, todo: Todo) -> Experience | None:
        """Extract structured experience from a completed todo's conversations."""
        conversations = await self.conv_repo.list_by_todo_id(todo.id)

        conversation_log = ""
        for conv in conversations:
            conversation_log += f"\n### {conv.purpose.value} 对话\n"
            for msg in conv.messages:
                if msg.role.value != "system":
                    role_label = "用户" if msg.role.value == "user" else "AI"
                    conversation_log += f"{role_label}: {msg.content}\n"

        if not conversation_log.strip():
            logger.info("extract_from_todo: no conversation content for todo %s", todo.id)
            return None

        prompt = EXTRACTION_PROMPT.format(
            title=todo.title,
            description=todo.description,
            background=getattr(todo, "background", ""),
            goals=getattr(todo, "goals", ""),
            tech_plan=getattr(todo, "tech_plan", ""),
            conversation_log=conversation_log,
        )

        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.ai.resilience import create_resilient_adapter

        adapter = create_resilient_adapter()
        try:
            response = await adapter.chat(
                [LLMMessage(role="user", content=prompt)],
                temperature=0.3,
            )

            data = extract_json(response.content)
            if not isinstance(data, dict):
                logger.error("extract_from_todo: JSON parse failed for todo %s", todo.id)
                return None

            tags = [
                Tag(label=t, color=TAG_COLORS.get(t, "#888888"))
                for t in data.get("tags", [])
            ]

            embedding_text = (
                f"{data.get('title', '')} {data.get('problem', '')} "
                f"{data.get('solution', '')} "
                f"{data.get('applicable_scenarios', '')}"
            )
            embedding = await adapter.embed(embedding_text)

            experience = Experience(
                todo_id=todo.id,
                project_id=todo.project_id,
                scope=ExperienceScope.PROJECT,
                status=ExperienceStatus.DRAFT,
                title=data.get("title", todo.title),
                problem=data.get("problem", ""),
                solution=data.get("solution", ""),
                decisions=data.get("decisions", []),
                pitfalls=data.get("pitfalls", []),
                applicable_scenarios=data.get("applicable_scenarios", ""),
                tags=tags,
                embedding=embedding,
                confidence=0.7,
            )

            created = await self.exp_repo.create(experience)
            logger.info("extract_from_todo: created experience %s for todo %s", created.id, todo.id)
            return created
        except Exception as exc:
            logger.error("extract_from_todo: unexpected error: %s", exc)
            return None
        finally:
            await adapter.close()

    async def search_similar(
        self, query: str, limit: int = 5, project_id: uuid.UUID | None = None,
    ) -> list[Experience]:
        """Search for related experiences using embedding similarity."""
        from arc.application.ai.resilience import create_resilient_adapter

        try:
            adapter = create_resilient_adapter()
        except Exception as exc:
            logger.warning("search_similar: adapter creation failed: %s", exc)
            return []
        try:
            embedding = await adapter.embed(query)
        except Exception as exc:
            logger.warning("search_similar: embedding generation failed: %s", exc)
            return []
        finally:
            await adapter.close()

        try:
            return await self.exp_repo.search_by_embedding(
                embedding, limit=limit, project_id=project_id,
            )
        except Exception as exc:
            logger.warning("search_similar: vector search failed: %s", exc)
            return []

    async def search_related(
        self, query_embedding: list[float], limit: int = 5
    ) -> list[Experience]:
        """Search for related experiences using pre-computed vector."""
        try:
            return await self.exp_repo.search_by_embedding(query_embedding, limit=limit)
        except Exception as exc:
            logger.warning("search_related: vector search failed: %s", exc)
            return []
