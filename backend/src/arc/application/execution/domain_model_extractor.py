"""从 tech_architecture 交付物中提取领域模型并合并到项目。"""

from __future__ import annotations

import copy
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
        """从 tech_architecture 内容提取战略设计+实体，合并到项目 domain_model。

        Returns True if domain_model was updated.
        """
        data_model = tech_arch_content.get("data_model")
        domain_design = tech_arch_content.get("domain_design")
        event_storming = tech_arch_content.get("event_storming")

        has_entities = (
            data_model
            and isinstance(data_model.get("entities"), list)
            and len(data_model["entities"]) > 0
        )
        has_strategic = domain_design and isinstance(domain_design, dict)
        has_events = event_storming and isinstance(event_storming, dict)

        if not has_entities and not has_strategic and not has_events:
            return False

        todo_repo = TodoRepository(self.db)
        todo = await todo_repo.get_by_id(todo_id)
        if not todo or not todo.project_id:
            return False

        project_repo = ProjectRepository(self.db)
        project = await project_repo.get_by_id(todo.project_id)
        if not project:
            return False

        dm = project.domain_model or {}
        snapshot = copy.deepcopy(dm)

        if has_entities:
            entities = data_model["entities"]
            contexts_map = self._build_entity_context_map(entities)
            new_aggregates = self._entities_to_aggregates(
                entities, todo.title, contexts_map
            )
            if new_aggregates:
                existing_aggs = dm.get("aggregates", [])
                dm["aggregates"] = self._merge_aggregates(
                    existing_aggs, new_aggregates,
                )

        if has_strategic:
            self._merge_strategic_design(dm, domain_design)

        if has_events:
            self._merge_event_storming(dm, event_storming)

        if self._models_equal(snapshot, dm):
            return False

        dm.setdefault("subdomains", [])
        dm.setdefault("contexts", [])
        dm.setdefault("aggregates", [])
        dm.setdefault("relations", [])
        dm.setdefault("aggregate_relations", [])
        dm["updated_at"] = datetime.now(UTC).isoformat()
        dm["version"] = dm.get("version", 0) + 1

        project.domain_model = dm
        await project_repo.update(project)

        logger.info(
            "Domain model updated for project %s: %d sub, %d ctx, %d agg (todo %s)",
            project.id,
            len(dm.get("subdomains", [])),
            len(dm.get("contexts", [])),
            len(dm.get("aggregates", [])),
            todo_id,
        )
        return True

    @staticmethod
    def _build_entity_context_map(entities: list[dict]) -> dict[str, str]:
        """从 entities 的 bounded_context 字段构建 name→context 映射。"""
        mapping: dict[str, str] = {}
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            name = entity.get("name", "")
            ctx = entity.get("bounded_context", "")
            if name and ctx:
                mapping[name] = ctx
        return mapping

    @staticmethod
    def _entities_to_aggregates(
        entities: list[dict], source_label: str, contexts_map: dict[str, str] | None = None
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
            context = (contexts_map or {}).get(name, "")

            aggregates.append({
                "name": name,
                "context": context,
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
    def _merge_strategic_design(dm: dict, domain_design: dict) -> None:
        """合并战略设计数据到领域模型。"""
        subdomains = domain_design.get("subdomains")
        if isinstance(subdomains, list) and subdomains:
            existing = {s.get("name"): s for s in dm.get("subdomains", [])}
            for sd in subdomains:
                if not isinstance(sd, dict) or not sd.get("name"):
                    continue
                existing[sd["name"]] = {
                    "name": sd["name"],
                    "type": sd.get("type", "核心域"),
                    "description": sd.get("description", ""),
                }
            dm["subdomains"] = list(existing.values())

        contexts = domain_design.get("bounded_contexts")
        if isinstance(contexts, list) and contexts:
            existing = {c.get("name"): c for c in dm.get("contexts", [])}
            for ctx in contexts:
                if not isinstance(ctx, dict) or not ctx.get("name"):
                    continue
                existing[ctx["name"]] = {
                    "name": ctx["name"],
                    "subdomain": ctx.get("subdomain", ""),
                    "description": ctx.get("description", ""),
                }
            dm["contexts"] = list(existing.values())

        relations = domain_design.get("context_relations")
        if isinstance(relations, list) and relations:
            existing = {
                (r.get("from"), r.get("to")): r for r in dm.get("relations", [])
            }
            for rel in relations:
                if not isinstance(rel, dict):
                    continue
                fr, to = rel.get("from", ""), rel.get("to", "")
                if not fr or not to:
                    continue
                existing[(fr, to)] = {
                    "from": fr,
                    "to": to,
                    "type": rel.get("type", ""),
                    "description": rel.get("description", ""),
                }
            dm["relations"] = list(existing.values())

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

    @staticmethod
    def _merge_event_storming(dm: dict, event_storming: dict) -> None:
        """将事件风暴数据合并到对应聚合的 events/methods 字段。"""
        agg_by_name: dict[str, dict] = {
            a.get("name", ""): a for a in dm.get("aggregates", [])
        }

        events = event_storming.get("events")
        if isinstance(events, list):
            for evt in events:
                if not isinstance(evt, dict):
                    continue
                agg_name = evt.get("aggregate", "")
                event_name = evt.get("name", "")
                if not event_name:
                    continue
                if agg_name and agg_name in agg_by_name:
                    agg_events = agg_by_name[agg_name].setdefault("events", [])
                    if event_name not in agg_events:
                        agg_events.append(event_name)

        commands = event_storming.get("commands")
        if isinstance(commands, list):
            for cmd in commands:
                if not isinstance(cmd, dict):
                    continue
                agg_name = cmd.get("target_aggregate", "")
                cmd_name = cmd.get("name", "")
                if not cmd_name:
                    continue
                if agg_name and agg_name in agg_by_name:
                    agg_methods = agg_by_name[agg_name].setdefault("methods", [])
                    if cmd_name not in agg_methods:
                        agg_methods.append(cmd_name)

    @staticmethod
    def _models_equal(before: dict, after: dict) -> bool:
        """比较合并前后领域模型是否实质相同（忽略元数据字段）。"""
        keys = ("subdomains", "contexts", "aggregates",
                "relations", "aggregate_relations")
        for k in keys:
            if before.get(k, []) != after.get(k, []):
                return False
        return True
