from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.ai.json_extract import extract_json
from arc.domain.experience.entity import Experience
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import (
    ExperienceCategory,
    ExperienceScope,
    ExperienceSource,
    ExperienceStatus,
    Tag,
)
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
  "category": "technical|business_rule|pitfall|architecture_decision",
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

            try:
                category = ExperienceCategory(data.get("category", "technical"))
            except ValueError:
                category = ExperienceCategory.TECHNICAL

            experience = Experience(
                todo_id=todo.id,
                project_id=todo.project_id,
                version_id=todo.version_id,
                scope=ExperienceScope.PROJECT,
                status=ExperienceStatus.DRAFT,
                category=category,
                source=ExperienceSource.TODO_COMPLETION,
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
        self, query: str, limit: int = 5,
        project_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
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
                embedding, limit=limit, project_id=project_id, user_id=user_id,
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

    async def decay_batch(self) -> int:
        entities = await self.exp_repo.list_for_decay()
        if not entities:
            return 0

        updates: list[tuple[uuid.UUID, float]] = []
        for exp in entities:
            decayed = exp.compute_decayed_confidence()
            if abs(decayed - exp.confidence) > 0.001:
                updates.append((exp.id, decayed))

        if not updates:
            return 0

        count = await self.exp_repo.batch_update_confidence(updates)
        await self.db.commit()
        logger.info("decay_batch: updated %d experiences", count)
        return count

    async def distill_to_personal(self, experience_id: uuid.UUID, user_id: uuid.UUID | None = None) -> Experience:
        exp = await self.exp_repo.get_by_id(experience_id, user_id=user_id)
        if not exp:
            raise ValueError("Experience not found")
        if exp.scope == ExperienceScope.PERSONAL:
            raise ValueError("Already a personal experience")

        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.ai.resilience import create_resilient_adapter

        distill_prompt = (
            f"将以下项目经验提炼为通用个人经验。去除项目特定细节，提取可复用的通用模式。\n\n"
            f"标题: {exp.title}\n问题: {exp.problem}\n方案: {exp.solution}\n"
            f"决策: {', '.join(exp.decisions)}\n踩坑: {', '.join(exp.pitfalls)}\n"
            f"适用场景: {exp.applicable_scenarios}\n\n"
            f"请以JSON格式输出：\n"
            f'{{"title": "通用标题", "problem": "通用问题描述", "solution": "通用方案", '
            f'"applicable_scenarios": "适用场景"}}\n只输出JSON。'
        )

        distilled_data = {}
        try:
            adapter = create_resilient_adapter()
            try:
                response = await adapter.chat(
                    [LLMMessage(role="user", content=distill_prompt)],
                    temperature=0.3,
                )
                from arc.application.ai.json_extract import extract_json
                distilled_data = extract_json(response.content)
                if not isinstance(distilled_data, dict):
                    distilled_data = {}
            finally:
                await adapter.close()
        except Exception as exc:
            logger.warning("distill_to_personal: AI distill failed: %s, using original content", exc)

        personal = Experience(
            title=distilled_data.get("title", exp.title),
            problem=distilled_data.get("problem", exp.problem),
            solution=distilled_data.get("solution", exp.solution),
            project_id=None,
            version_id=None,
            source_experience_id=exp.id,
            scope=ExperienceScope.PERSONAL,
            status=ExperienceStatus.DRAFT,
            category=exp.category,
            source=exp.source,
            decisions=exp.decisions,
            pitfalls=exp.pitfalls,
            applicable_scenarios=distilled_data.get("applicable_scenarios", exp.applicable_scenarios),
            tags=exp.tags,
            confidence=exp.confidence,
        )

        created = await self.exp_repo.create(personal, user_id=user_id)
        logger.info("distill_to_personal: created personal exp %s from %s", created.id, experience_id)
        return created
