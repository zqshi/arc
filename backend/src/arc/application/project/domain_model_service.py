"""项目领域模型管理 — 获取、刷新、从代码提取、合并。"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.errors import AppError, NotFoundError
from arc.domain.project.entity import Project
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.project import ProjectRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)

EMPTY_DOMAIN_MODEL = {
    "subdomains": [],
    "contexts": [],
    "aggregates": [],
    "relations": [],
    "aggregate_relations": [],
}


class DomainModelService:
    """编排项目领域模型的获取、刷新和代码提取逻辑。"""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._project_repo = ProjectRepository(db)
        self._todo_repo = TodoRepository(db)
        self._artifact_repo = ArtifactRepository(db)

    async def get_domain_model(
        self, project: Project, user_id: uuid.UUID
    ) -> dict:
        """获取项目领域模型，如果不存在则尝试从 artifact 中提取。

        Returns:
            领域模型 dict，包含 aggregates/subdomains 等字段。
            如果无任何数据，附加 _hint 提示前端。
        """
        dm = project.domain_model
        if dm and (dm.get("aggregates") or dm.get("subdomains")):
            return dm

        # Fallback: 从 tech_architecture artifacts 提取
        dm = await self._extract_from_artifacts(project, user_id)

        result = dm or {**EMPTY_DOMAIN_MODEL}

        if not result.get("aggregates") and not result.get("subdomains"):
            todos, _ = await self._todo_repo.list_all(
                project_id=project.id, user_id=user_id, offset=0, limit=1,
            )
            result["_hint"] = {
                "has_local_path": bool(project.local_path),
                "has_codebase_summary": bool(project.codebase_summary),
                "has_todos": len(todos) > 0 if todos else False,
            }

        return result

    async def refresh_domain_model(
        self, project: Project, user_id: uuid.UUID
    ) -> tuple[int, dict]:
        """扫描所有 tech_architecture artifacts，全量合并到领域模型。

        Returns:
            (merged_count, domain_model_dict)
        """
        from arc.application.execution.domain_model_extractor import DomainModelExtractor

        extractor = DomainModelExtractor(self._db)

        todos, _ = await self._todo_repo.list_all(
            project_id=project.id, user_id=user_id, offset=0, limit=500,
        )
        todo_ids = [t.id for t in todos]
        arts_by_todo = await self._artifact_repo.list_by_todo_ids(todo_ids)

        merged = 0
        for todo in todos:
            for art in arts_by_todo.get(todo.id, []):
                if art.artifact_type.value != "tech_architecture":
                    continue
                data_model = art.content.get("data_model")
                domain_design = art.content.get("domain_design")
                has_model = (
                    isinstance(data_model, dict)
                    and isinstance(data_model.get("entities"), list)
                    and len(data_model["entities"]) > 0
                ) or (isinstance(domain_design, dict) and bool(domain_design))
                if not has_model:
                    continue
                updated = await extractor.extract_and_merge(todo.id, art.content)
                if updated:
                    merged += 1

        await self._db.commit()
        refreshed_project = await self._project_repo.get_by_id(project.id, user_id=user_id)
        dm = refreshed_project.domain_model or {**EMPTY_DOMAIN_MODEL}
        # v6.24 P0-1: refresh 提取后自动 provision BaaS (之前 pipeline 路径不触发 provision)
        if merged:
            try:
                await self.provision_baas(project.id)
            except Exception:
                logger.warning(
                    "refresh 后 BaaS provision 失败 project %s", project.id, exc_info=True
                )
        return merged, dm

    async def provision_baas(self, project_id: uuid.UUID) -> dict:
        """从 project.domain_model provision BaaS (v6.24 P0-1)。

        pipeline/refresh/手动端点的统一 provision 入口 (之前 BaaS provision 只挂
        conversation 模式 artifact_extractor 链, pipeline 主路径不触发)。无 domain_model
        或无聚合则跳过。apply 失败抛异常 (调用方决定 graceful)。

        Returns: {provisioned: bool, reason?/reason_code?/schema_name?}
            - reason_code (英文, 供 metrics/编程消费): no_domain_model / no_aggregates
            - reason (中文, 供前端展示)
        """
        project = await self._project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        dm = project.domain_model
        if not dm:
            return {"provisioned": False, "reason": "项目无领域模型",
                    "reason_code": "no_domain_model"}
        aggregates = dm.get("aggregates", []) if isinstance(dm, dict) else []
        if not aggregates:
            return {"provisioned": False, "reason": "领域模型无聚合",
                    "reason_code": "no_aggregates"}

        from arc.application.baas.domain_model_applier import DomainModelApplier
        from arc.application.baas.service import BaasService
        from arc.domain.project.value_objects import (
            DomainModelSnapshot,
            ModelChangeTrigger,
        )

        snapshot = DomainModelSnapshot(
            version=dm.get("version", 1),
            content=dm,
            trigger=ModelChangeTrigger.MANUAL,
            trigger_todo_id=None,
            created_at=datetime.now(UTC),
        )
        baas_service = BaasService(self._db)
        applier = DomainModelApplier(baas_service)
        await applier.apply_snapshot(
            project_id=project.id,
            snapshot=snapshot,
            supabase_url="",  # dev 同库隔离; 投产由 SupabaseClient 按配置解析
        )
        logger.info("BaaS provisioned for project %s", project.id)
        return {
            "provisioned": True,
            "schema_name": DomainModelApplier._schema_name_for(project.id),
        }

    async def extract_from_code(self, project: Project) -> dict:
        """从代码库源文件直接提取领域模型并合并。

        Raises:
            ValueError: 当目录不存在或无可分析源码时。
            RuntimeError: 当 AI 返回格式无法解析时。

        Returns:
            更新后的 domain_model dict。
        """
        from pathlib import Path

        from arc.application.ai.adapter_pool import adapter_pool
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.project.scanner import CodebaseScanner
        from arc.application.project.scanner_analysis import (
            build_domain_model_prompt,
            parse_domain_model_response,
        )

        if not project.local_path:
            raise AppError("请先配置本地工作目录")

        path = Path(project.local_path).expanduser().resolve()
        if not path.is_dir():
            raise NotFoundError(f"目录不存在: {project.local_path}")

        # 扫描并构建 prompt
        scanner = CodebaseScanner(str(path))
        data = scanner.full_scan()
        prompt = build_domain_model_prompt(data)
        if not prompt:
            raise NotFoundError("未找到可分析的源码文件")

        # LLM 调用
        async with adapter_pool.acquire() as adapter:
            response = await adapter.chat(
                [LLMMessage(role="user", content=prompt)],
                temperature=0.1,
                max_tokens=8192,
            )

        domain_model = parse_domain_model_response(response.content)
        if not domain_model:
            raise RuntimeError("领域模型提取失败：AI 返回格式无法解析")

        # 合并到现有模型
        existing_dm = project.domain_model or {}
        if not existing_dm.get("aggregates") and not existing_dm.get("subdomains"):
            domain_model["updated_at"] = datetime.now(UTC).isoformat()
            domain_model["version"] = 1
            domain_model["source"] = "codebase_scan"
            project.domain_model = domain_model
        else:
            from arc.application.project.scan_task import ScanTaskManager
            ScanTaskManager._merge_domain_model(existing_dm, domain_model)
            existing_dm["updated_at"] = datetime.now(UTC).isoformat()
            existing_dm["version"] = existing_dm.get("version", 0) + 1
            project.domain_model = existing_dm

        await self._project_repo.update(project)
        await self._db.commit()

        return project.domain_model

    async def _extract_from_artifacts(
        self, project: Project, user_id: uuid.UUID
    ) -> dict | None:
        """从已有 tech_architecture artifacts 中尝试提取领域模型。"""
        from arc.application.execution.domain_model_extractor import DomainModelExtractor

        todos, _ = await self._todo_repo.list_all(
            project_id=project.id, user_id=user_id, offset=0, limit=100,
        )
        if not todos:
            return None

        arts_map = await self._artifact_repo.list_by_todo_ids([t.id for t in todos])
        for todo in todos:
            for art in arts_map.get(todo.id, []):
                if art.artifact_type.value != "tech_architecture":
                    continue
                data_model = art.content.get("data_model")
                domain_design = art.content.get("domain_design")
                has_entities = (
                    isinstance(data_model, dict)
                    and isinstance(data_model.get("entities"), list)
                    and len(data_model["entities"]) > 0
                )
                has_design = isinstance(domain_design, dict) and bool(domain_design)
                if not has_entities and not has_design:
                    continue
                extractor = DomainModelExtractor(self._db)
                updated = await extractor.extract_and_merge(todo.id, art.content)
                if updated:
                    await self._db.commit()
                    refreshed = await self._project_repo.get_by_id(
                        project.id, user_id=user_id,
                    )
                    dm = refreshed.domain_model
                    if dm and (dm.get("aggregates") or dm.get("subdomains")):
                        return dm

        return project.domain_model
