from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import Tag
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)

TAG_EXTRACTION_PROMPT = """根据以下待办事项的标题和描述，自动提取2-4个分类标签。

标题: {title}
描述: {description}

要求：
- 每个标签2-4个字
- 标签应反映：技术领域（前端/后端/数据库/AI等）、任务类型（功能/修复/优化/重构等）、或业务领域
- 为每个标签指定一个合适的颜色（hex格式，使用柔和色调）
- 只输出JSON数组，不要其他内容

[
  {{"label": "标签名", "color": "#hex颜色"}},
  ...
]"""


class TodoService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.todo_repo = TodoRepository(db)

    async def create_todo(self, todo: Todo) -> Todo:
        return await self.todo_repo.create(todo)

    async def extract_tags(self, todo_id: uuid.UUID) -> Todo:
        """Use LLM to extract tags from todo title+description."""
        todo = await self.todo_repo.get_by_id(todo_id)
        if not todo:
            raise ValueError(f"Todo {todo_id} not found")

        from arc.application.ai.adapter_pool import adapter_pool
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.llm.service import LLMProviderService
        from arc.infrastructure.repositories.project import ProjectRepository

        # v6.21 D1: LLM 凭证走 DB (项目级 llm_provider_id → 用户默认), 非 env fallback
        llm_config = None
        if todo.project_id:
            project = await ProjectRepository(self.db).get_by_id(todo.project_id)
            if project:
                llm_config = await LLMProviderService(self.db).resolve_from_project(
                    project, project.user_id
                )

        async with adapter_pool.acquire_for_project(llm_config) as adapter:
            try:
                prompt = TAG_EXTRACTION_PROMPT.format(
                    title=todo.title,
                    description=todo.description or "（无描述）",
                )
                response = await adapter.chat(
                    [LLMMessage(role="user", content=prompt)],
                    temperature=0.3,
                    max_tokens=512,
                )
                tags = self._parse_tags(response.content)
                todo.tags = tags
                await self.todo_repo.update(todo)
                logger.info("Extracted %d tags for todo %s", len(tags), todo_id)
            except Exception as exc:
                logger.warning("Tag extraction failed for todo %s: %s", todo_id, exc)

        return todo

    @staticmethod
    def _parse_tags(content: str) -> list[Tag]:
        """Parse LLM response into Tag list, tolerating markdown wrapping."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            end = text.rfind("]")
            if start == -1 or end == -1:
                return []
            raw = json.loads(text[start : end + 1])
        tags = []
        for item in raw[:4]:
            if isinstance(item, dict) and "label" in item:
                tags.append(
                    Tag(
                        label=str(item["label"])[:10],
                        color=str(item.get("color", "#4A9FD8")),
                    )
                )
        return tags
