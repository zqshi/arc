"""从 tech_architecture 交付物中提取领域模型并合并到项目。"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from arc.infrastructure.repositories.project import ProjectRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


class DomainModelExtractor:
    """从 tech_architecture artifact 的 data_model 字段提取聚合信息，
    合并到项目级 domain_model JSONB。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def extract_and_merge(
        self,
        todo_id: uuid.UUID,
        tech_arch_content: dict,
    ) -> bool:
        """从 tech_architecture 内容提取实体，合并到项目 domain_model。

        Returns True if domain_model was updated.
        """
        data_model = tech_arch_content.get("data_model")
        if not data_model:
            return False

        entities = data_model.get("entities")
        if not entities or not isinstance(entities, list):
            return False

        todo_repo = TodoRepository(self.db)
        todo = await todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return False

        project_repo = ProjectRepository(self.db)
        project = await project_repo.get_by_id(todo.project_id)
        if not project:
            return False

        new_aggregates = self._entities_to_aggregates(entities, todo.title)
        if not new_aggregates:
            return False

        dm = project.domain_model or {}
        existing_aggs = dm.get("aggregates", [])
        merged = self._merge_aggregates(existing_aggs, new_aggregates)

        dm["aggregates"] = merged
        dm.setdefault("subdomains", [])
        dm.setdefault("contexts", [])
        dm.setdefault("relations", [])
        dm.setdefault("aggregate_relations", [])
        dm["updated_at"] = datetime.now(UTC).isoformat()
        dm["version"] = dm.get("version", 0) + 1

        project.domain_model = dm
        await project_repo.update(project)

        logger.info(
            "Domain model updated for project %s: %d aggregates (from todo %s)",
            project.id,
            len(merged),
            todo_id,
        )
        return True

    @staticmethod
    def _entities_to_aggregates(
        entities: list[dict], source_label: str
    ) -> list[dict]:
        aggregates = []
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            name = entity.get("name")
            if not name:
                continue

            fields = entity.get("fields", [])
            field_names = [
                f.get("name", "") for f in fields if isinstance(f, dict)
            ]
            relations_desc = entity.get("relations", "")

            aggregates.append({
                "name": name,
                "context": "",
                "description": relations_desc or f"来自: {source_label}",
                "root": name,
                "entities": [],
                "value_objects": [],
                "events": [],
                "methods": [],
                "fields": field_names,
                "source": source_label,
            })
        return aggregates

    @staticmethod
    def _merge_aggregates(
        existing: list[dict], new: list[dict]
    ) -> list[dict]:
        by_name: dict[str, dict] = {}
        for agg in existing:
            by_name[agg.get("name", "")] = agg

        for agg in new:
            name = agg.get("name", "")
            if name in by_name:
                old = by_name[name]
                old["fields"] = agg.get("fields", old.get("fields", []))
                old["description"] = agg.get("description") or old.get("description", "")
                old["source"] = agg.get("source", old.get("source", ""))
            else:
                by_name[name] = agg

        return list(by_name.values())
