from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.errors import AppError, NotFoundError
from arc.domain.project.entity import Version
from arc.infrastructure.repositories.project import VersionRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


def _next_version_name(existing_versions: list[Version], version_type: str) -> str:
    latest = (0, 0, 0)
    for v in existing_versions:
        m = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$", v.name)
        if m:
            parsed = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
            if parsed > latest:
                latest = parsed

    major, minor, patch = latest
    if major == 0 and minor == 0 and patch == 0:
        if version_type == "major":
            return "v1.0"
        return "v0.1"

    if version_type == "major":
        return f"v{major + 1}.0"
    if version_type == "minor":
        return f"v{major}.{minor + 1}"
    return f"v{major}.{minor}.{patch + 1}"


class VersionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.version_repo = VersionRepository(db)
        self.todo_repo = TodoRepository(db)

    async def compute_analysis_status(
        self, versions: list[Version]
    ) -> dict[uuid.UUID, dict]:
        """计算版本分析状态: {version_id: {has: bool, stale: bool}}。

        比对 version_analyses 表存的 fingerprint 与按当前 todo 状态重算的 fingerprint,
        不一致则 stale (todo 变更后分析过期)。兼容表不存在的情况 (DDL 兜底建表)。

        v6.19 质检 P1: 从 routes/project/versions.py 下沉 — 原 route handler 含
        fingerprint 计算 + stale 判定 + DDL 建表回退, 违反 route 层零逻辑。
        """
        analysis_info: dict[uuid.UUID, dict] = {}
        try:
            import hashlib

            from sqlalchemy import select

            from arc.infrastructure.models.planning import VersionAnalysisModel
            from arc.infrastructure.models.todo import Todo as TodoModel

            version_ids = [v.id for v in versions]
            if version_ids:
                # 获取每个版本最新分析的 fingerprint（兼容写法，不用 DISTINCT ON）
                result = await self.db.execute(
                    select(VersionAnalysisModel.version_id, VersionAnalysisModel.fingerprint)
                    .where(VersionAnalysisModel.version_id.in_(version_ids))
                    .order_by(VersionAnalysisModel.created_at.desc())
                )
                # 取每个 version_id 的第一条（最新）
                latest_fps: dict[uuid.UUID, str] = {}
                for row in result.all():
                    if row[0] not in latest_fps:
                        latest_fps[row[0]] = row[1]

                # 计算每个版本的当前 fingerprint
                for v in versions:
                    vid = v.id
                    if vid not in latest_fps:
                        analysis_info[vid] = {"has": False, "stale": False}
                        continue
                    todo_result = await self.db.execute(
                        select(TodoModel.id, TodoModel.status)
                        .where(TodoModel.version_id == vid)
                        .order_by(TodoModel.id)
                    )
                    parts = sorted(f"{r[0]}:{r[1]}" for r in todo_result.all())
                    current_fp = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
                    analysis_info[vid] = {
                        "has": True,
                        "stale": current_fp != latest_fps[vid],
                    }
        except Exception:
            # 表可能不存在 — 尝试自动创建 (历史兼容)
            try:
                await self.db.rollback()
                from sqlalchemy import text
                await self.db.execute(text(
                    "CREATE TABLE IF NOT EXISTS version_analyses ("
                    "id UUID PRIMARY KEY DEFAULT gen_random_uuid(), "
                    "version_id UUID NOT NULL REFERENCES versions(id) ON DELETE CASCADE, "
                    "fingerprint VARCHAR(64) NOT NULL, "
                    "content TEXT NOT NULL, "
                    "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
                    "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"
                ))
                await self.db.commit()
            except Exception:
                try:
                    await self.db.rollback()
                except Exception:
                    pass
        return analysis_info

    async def create_version(
        self,
        project_id: uuid.UUID,
        *,
        name: str | None = None,
        goal: str = "",
        version_type: str = "minor",
        parent_version_id: uuid.UUID | None = None,
    ) -> Version:
        next_order = await self.version_repo._next_order(project_id)

        if name and name.strip():
            resolved_name = name.strip()
        else:
            all_versions = await self.version_repo.list_by_project(project_id)
            resolved_name = _next_version_name(all_versions, version_type)

        version = Version(
            project_id=project_id,
            name=resolved_name,
            goal=goal,
            order=next_order,
            parent_version_id=parent_version_id,
        )
        return await self.version_repo.create(version)

    async def delete_version(self, project_id: uuid.UUID, version_id: uuid.UUID) -> None:
        version = await self._get_version(project_id, version_id)
        if version.status.value == "released":
            raise AppError("已发布版本不可删除")
        stats = await self.version_repo.count_todos_by_status(version_id)
        if sum(stats.values()) > 0:
            raise AppError("请先删除版本下的需求后再删除版本")
        await self.version_repo.delete(version_id)

    async def activate_version(self, project_id: uuid.UUID, version_id: uuid.UUID) -> Version:
        version = await self._get_version(project_id, version_id)

        stats = await self.version_repo.count_todos_by_status(version_id)
        total = sum(stats.values())
        if total == 0:
            raise AppError("版本下没有需求，无法激活")

        version.activate()
        await self.version_repo.update(version)
        return version

    async def release_version(
        self, project_id: uuid.UUID, version_id: uuid.UUID
    ) -> tuple[Version, Version | None]:
        version = await self._get_version(project_id, version_id)

        stats = await self.version_repo.count_todos_by_status(version_id)
        incomplete = stats.get("pending", 0) + stats.get("active", 0) + stats.get("error", 0)
        if incomplete > 0:
            raise AppError(f"还有 {incomplete} 条未完成需求，无法发布")

        version.release()

        todos, _ = await self.todo_repo.list_all(version_id=version_id, limit=10000)
        done_todos = [t for t in todos if t.status.value == "done"]

        # AI 生成 changelog，失败时降级为简单列表
        changelog = await self._generate_changelog(version, done_todos)
        if changelog:
            version.set_changelog(changelog)

        # 自动生成原型快照（snapshot）
        await self._snapshot_prototype(project_id, version_id, version)

        # v5.7.0: 版本发布后自动从领域模型提取可复用模板草稿
        await self._extract_template_after_release(project_id, version_id)

        await self.version_repo.update(version)

        carry_over_version = await self._carry_over_todos(version)
        return version, carry_over_version

    async def _snapshot_prototype(
        self, project_id: uuid.UUID, version_id: uuid.UUID, version: "Version"
    ) -> None:
        """版本发布时记录原型快照。

        工程模式下每次部署都有独立 deploy_id，URL 天然不可变，
        只需确认当前 prototype_preview_url 已设置即可。
        """
        import logging

        logger = logging.getLogger(__name__)
        try:
            from arc.application.artifact.prototype_bundle import PrototypeBundleService

            svc = PrototypeBundleService(self.db)
            bundle = await svc.build_bundle(project_id, version_id=version_id)
            if bundle.preview_url and not version.prototype_preview_url:
                version.set_prototype_preview_url(bundle.preview_url)
                logger.info("Prototype snapshot for version %s: %s", version_id, bundle.preview_url)
        except Exception as exc:
            logger.warning("Failed to snapshot prototype for version %s: %s", version_id, exc)

    async def _extract_template_after_release(
        self, project_id: uuid.UUID, version_id: uuid.UUID
    ) -> None:
        """v5.7.0: 版本发布后从项目领域模型提取可复用模板草稿 (draft)。

        流程: project.domain_model → BaasSchema (applier 转换) →
        TemplateExtractionService.extract_template → 保存 draft 模板。
        失败仅 warning 不阻断 release (模板提取是增值, 非发布必需)。
        """
        try:
            from arc.infrastructure.repositories.project import ProjectRepository

            project = await ProjectRepository(self.db).get_by_id(project_id)
            if not project or not project.domain_model:
                return

            dm = project.domain_model
            aggregates = dm.get("aggregates", []) if isinstance(dm, dict) else []
            if not aggregates:
                logger.info(
                    "Template extraction skipped: project %s 无聚合", project_id
                )
                return

            # domain_model → BaasSchema (复用 v5.6.0 applier 的纯转换)
            from datetime import UTC, datetime

            from arc.domain.project.value_objects import (
                DomainModelSnapshot,
                ModelChangeTrigger,
            )

            snapshot = DomainModelSnapshot(
                version=dm.get("version", 1),
                content=dm,
                trigger=ModelChangeTrigger.MANUAL,
                trigger_todo_id="",
                created_at=datetime.now(UTC),
            )
            from arc.application.baas.domain_model_applier import (
                DomainModelApplier,
            )

            baas_schema = DomainModelApplier.convert_to_baas_schema(
                snapshot, project_id=project_id
            )

            # 提取模板 (LLM 生成标题/描述)
            from arc.application.template.extraction_service import (
                TemplateExtractionService,
            )
            from arc.infrastructure.repositories.template import TemplateRepository

            source_user_id = project.user_id or uuid.UUID(int=0)
            extraction = TemplateExtractionService()
            template = await extraction.extract_template(
                schema=baas_schema,
                source_user_id=source_user_id,
                source_project_id=project_id,
                source_version_id=version_id,
            )
            await TemplateRepository(self.db).create(template)
            logger.info(
                "Template extracted after release: project=%s → template %s (draft)",
                project_id, template.id,
            )
        except Exception:
            logger.warning(
                "Template extraction failed for project %s version %s",
                project_id, version_id, exc_info=True,
            )

    async def _generate_changelog(
        self, version: Version, done_todos: list
    ) -> str:
        """AI 生成版本 changelog，失败时降级为 bullet list。"""
        if not done_todos:
            return ""

        # 构建 fallback
        fallback = "\n".join(f"- {t.title}" for t in done_todos)

        # 构建 LLM prompt
        todo_details = []
        for t in done_todos:
            line = f"- {t.title}"
            if t.description:
                line += f"\n  描述: {t.description[:200]}"
            todo_details.append(line)

        prompt = (
            f"你是一个产品经理，正在为版本 {version.name} 生成变更日志。\n\n"
            f"版本目标: {version.goal or '未指定'}\n\n"
            f"本版本完成的需求:\n{''.join(todo_details)}\n\n"
            "请生成一段简洁的中文变更日志（changelog），要求:\n"
            "1. 按功能类别分组（如: 新功能、优化、修复）\n"
            "2. 每条用 `- ` 开头，一句话概括\n"
            "3. 整体不超过 500 字\n"
            "4. 不要输出标题（如「变更日志」），直接输出内容\n"
            "5. 用户能从中快速了解这个版本做了什么"
        )

        try:
            from arc.application.ai.llm_adapter import LLMMessage
            from arc.application.ai.resilience import create_resilient_adapter

            adapter = create_resilient_adapter()
            try:
                response = await adapter.chat([LLMMessage(role="user", content=prompt)])
                if response.content and len(response.content.strip()) > 10:
                    return response.content.strip()
            finally:
                await adapter.close()
        except Exception:
            logger.debug("AI changelog generation failed, using fallback", exc_info=True)

        return fallback

    async def _carry_over_todos(self, released_version: Version) -> Version | None:
        todos, _ = await self.todo_repo.list_all(version_id=released_version.id, limit=10000)
        pending_todos = [t for t in todos if t.status.value != "done"]

        if not pending_todos:
            return None

        target = await self.version_repo.get_latest_planning(released_version.project_id)
        if not target:
            target = Version(
                project_id=released_version.project_id,
                name=f"{released_version.name}-next",
                parent_version_id=released_version.id,
            )
            target = await self.version_repo.create(target)

        for todo in pending_todos:
            todo.version_id = target.id
            await self.todo_repo.update(todo)

        return target

    async def _get_version(self, project_id: uuid.UUID, version_id: uuid.UUID) -> Version:
        version = await self.version_repo.get_by_id(version_id)
        if not version or version.project_id != project_id:
            raise NotFoundError("版本不存在")
        return version
