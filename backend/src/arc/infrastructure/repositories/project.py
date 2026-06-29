from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.project.charter import ProjectCharter
from arc.domain.project.entity import Project, Version
from arc.domain.project.repository import AbstractProjectRepository, AbstractVersionRepository
from arc.domain.project.value_objects import (
    DEFAULT_CONVERSATION_CONFIG,
    DEFAULT_PIPELINE_CONFIG,
    ContextPolicy,
    ProcessConfig,
    ProcessConstraint,
    ProjectStatus,
    ProjectType,
    VersionStatus,
)
from arc.infrastructure.models.project import ProjectModel, VersionModel
from arc.infrastructure.models.todo import Todo as TodoModel
from arc.infrastructure.models.user import ProjectMemberModel


class ProjectRepository(AbstractProjectRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, project: Project, user_id: uuid.UUID | None = None) -> Project:
        model = ProjectModel(
            id=project.id,
            organization_id=project.organization_id,
            user_id=user_id,
            name=project.name,
            description=project.description,
            tech_stack=project.tech_stack,
            project_type=project.project_type.value,
            repo_url=project.repo_url,
            local_path=project.local_path,
            conventions=project.conventions,
            codebase_summary=project.codebase_summary,
            scan_fingerprint=project.scan_fingerprint,
            status=project.status.value,
            process_constraint=project.process_constraint.value,
            process_config=project.process_config.to_dict() if project.process_config else None,
            pipeline_config=project.pipeline_config,
            conversation_config=project.conversation_config,
            domain_model=project.domain_model or None,
            domain_model_history=project.domain_model_history or [],
            context_policy=project.context_policy.to_dict() if project.context_policy else None,
            charter=project.charter.to_dict() if project.charter else None,
        )
        self.db.add(model)
        await self.db.flush()
        # 回填 user_id 到实体 (供后续提取等流程使用)
        project.user_id = user_id
        return project

    async def get_by_id(
        self,
        project_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> Project | None:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        if organization_id:
            stmt = stmt.where(ProjectModel.organization_id == organization_id)
        if user_id:
            member_project_ids = (
                select(ProjectMemberModel.project_id)
                .where(ProjectMemberModel.user_id == user_id)
                .scalar_subquery()
            )
            stmt = stmt.where(
                or_(
                    ProjectModel.user_id == user_id,
                    ProjectModel.id.in_(member_project_ids),
                )
            )
        result = await self.db.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_entity(model)

    async def list_all(
        self,
        include_archived: bool = False,
        user_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> list[Project]:
        stmt = select(ProjectModel).order_by(ProjectModel.created_at.desc())
        if organization_id:
            stmt = stmt.where(ProjectModel.organization_id == organization_id)
        if user_id:
            member_project_ids = (
                select(ProjectMemberModel.project_id)
                .where(ProjectMemberModel.user_id == user_id)
                .scalar_subquery()
            )
            stmt = stmt.where(
                or_(
                    ProjectModel.user_id == user_id,
                    ProjectModel.id.in_(member_project_ids),
                )
            )
        if not include_archived:
            stmt = stmt.where(ProjectModel.status != "archived")
        stmt = stmt.where(ProjectModel.status != "deleted")
        result = await self.db.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, project: Project) -> None:
        result = await self.db.execute(select(ProjectModel).where(ProjectModel.id == project.id))
        model = result.scalar_one_or_none()
        if not model:
            return
        model.name = project.name
        model.description = project.description
        model.tech_stack = project.tech_stack
        model.project_type = project.project_type.value
        model.repo_url = project.repo_url
        model.local_path = project.local_path
        model.conventions = project.conventions
        model.codebase_summary = project.codebase_summary
        model.scan_fingerprint = project.scan_fingerprint
        model.scan_status = project.scan_status
        model.scan_progress = project.scan_progress or None
        model.scan_error = project.scan_error or None
        model.status = project.status.value
        model.process_constraint = project.process_constraint.value
        model.process_config = project.process_config.to_dict() if project.process_config else None
        model.pipeline_config = project.pipeline_config
        model.conversation_config = project.conversation_config
        model.domain_model = project.domain_model or None
        model.domain_model_history = project.domain_model_history or []
        model.context_policy = project.context_policy.to_dict() if project.context_policy else None
        model.charter = project.charter.to_dict() if project.charter else None
        model.github_token = project.github_token or None
        model.github_webhook_secret = project.github_webhook_secret or None
        model.github_config = project.github_config or None
        model.enc_apple_creds = project.enc_apple_creds or None
        model.enc_win_creds = project.enc_win_creds or None
        model.enc_android_creds = project.enc_android_creds or None
        model.enc_appstore_creds = project.enc_appstore_creds or None
        model.enc_playstore_creds = project.enc_playstore_creds or None
        model.enc_tauri_updater_creds = project.enc_tauri_updater_creds or None
        model.deleted_at = project.deleted_at
        await self.db.flush()

    async def delete(self, project_id: uuid.UUID) -> bool:
        result = await self.db.execute(select(ProjectModel).where(ProjectModel.id == project_id))
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.db.delete(model)
        await self.db.flush()
        return True

    @staticmethod
    def _to_entity(model: ProjectModel) -> Project:
        return Project(
            id=model.id,
            user_id=model.user_id,
            organization_id=model.organization_id,
            name=model.name,
            description=model.description or "",
            tech_stack=model.tech_stack or "",
            repo_url=model.repo_url or "",
            local_path=model.local_path or "",
            conventions=model.conventions or "",
            codebase_summary=model.codebase_summary or "",
            scan_fingerprint=model.scan_fingerprint or "",
            scan_status=model.scan_status or "idle",
            scan_progress=model.scan_progress or "",
            scan_error=model.scan_error or "",
            status=ProjectStatus(model.status),
            process_constraint=ProcessConstraint(model.process_constraint)
            if getattr(model, "process_constraint", None)
            else ProcessConstraint.FREE,
            project_type=ProjectType(model.project_type)
            if getattr(model, "project_type", None)
            else ProjectType.STATIC_SITE,
            process_config=ProcessConfig.from_dict(model.process_config)
            if getattr(model, "process_config", None)
            else ProcessConfig(),
            pipeline_config=model.pipeline_config or dict(DEFAULT_PIPELINE_CONFIG),
            conversation_config=ProjectRepository._merge_conversation_config(
                model.conversation_config
            ),
            domain_model=model.domain_model or {},
            domain_model_history=model.domain_model_history or [],
            context_policy=ContextPolicy.from_dict(
                getattr(model, "context_policy", None)
            ),
            charter=ProjectCharter.from_dict(getattr(model, "charter", None)),
            github_token=model.github_token or "",
            github_webhook_secret=model.github_webhook_secret or "",
            github_config=model.github_config or {},
            enc_apple_creds=model.enc_apple_creds or "",
            enc_win_creds=model.enc_win_creds or "",
            enc_android_creds=model.enc_android_creds or "",
            enc_appstore_creds=model.enc_appstore_creds or "",
            enc_playstore_creds=model.enc_playstore_creds or "",
            enc_tauri_updater_creds=model.enc_tauri_updater_creds or "",
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _merge_conversation_config(stored: dict | None) -> dict:
        """Merge stored config with defaults, using canonical order from defaults."""
        base = dict(DEFAULT_CONVERSATION_CONFIG)
        if not stored:
            return base
        merged = {**base, **stored}
        default_deliverables = DEFAULT_CONVERSATION_CONFIG["required_deliverables"]
        stored_deliverables = set(stored.get("required_deliverables") or [])
        full = list(default_deliverables)
        for d in stored_deliverables:
            if d not in full:
                full.append(d)
        merged["required_deliverables"] = full
        return merged


class VersionRepository(AbstractVersionRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, version: Version) -> Version:
        if version.order == 0:
            version.order = await self._next_order(version.project_id)

        exists = await self.db.execute(
            select(VersionModel.id).where(
                VersionModel.project_id == version.project_id,
                VersionModel.name == version.name,
            )
        )
        if exists.scalar_one_or_none():
            raise ValueError(f"版本名称 '{version.name}' 已存在")

        model = VersionModel(
            id=version.id,
            project_id=version.project_id,
            name=version.name,
            goal=version.goal,
            status=version.status.value,
            parent_version_id=version.parent_version_id,
            order=version.order,
            changelog=version.changelog or None,
        )
        self.db.add(model)
        await self.db.flush()
        return version

    async def _next_order(self, project_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.coalesce(func.max(VersionModel.order), 0) + 1).where(
                VersionModel.project_id == project_id
            )
        )
        return result.scalar_one()

    async def get_by_id(self, version_id: uuid.UUID) -> Version | None:
        result = await self.db.execute(select(VersionModel).where(VersionModel.id == version_id))
        model = result.scalar_one_or_none()
        if not model:
            return None
        return self._to_entity(model)

    async def list_by_project(
        self, project_id: uuid.UUID, *, skip: int = 0, limit: int = 200
    ) -> list[Version]:
        result = await self.db.execute(
            select(VersionModel)
            .where(VersionModel.project_id == project_id)
            .order_by(VersionModel.order.desc())
            .offset(skip)
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update(self, version: Version) -> None:
        result = await self.db.execute(select(VersionModel).where(VersionModel.id == version.id))
        model = result.scalar_one_or_none()
        if not model:
            return
        model.name = version.name
        model.goal = version.goal
        model.status = version.status.value
        model.parent_version_id = version.parent_version_id
        model.order = version.order
        model.changelog = version.changelog or None
        model.prototype_preview_url = version.prototype_preview_url or None
        model.deploy_url = version.deploy_url or None
        await self.db.flush()

    async def get_latest_planning(self, project_id: uuid.UUID) -> Version | None:
        result = await self.db.execute(
            select(VersionModel)
            .where(
                VersionModel.project_id == project_id,
                VersionModel.status == "planning",
            )
            .order_by(VersionModel.order.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def count_todos_by_status(self, version_id: uuid.UUID) -> dict[str, int]:
        result = await self.db.execute(
            select(TodoModel.status, func.count())
            .where(TodoModel.version_id == version_id)
            .group_by(TodoModel.status)
        )
        return dict(result.all())

    async def batch_count_todos_by_status(
        self,
        version_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, dict[str, int]]:
        if not version_ids:
            return {}
        result = await self.db.execute(
            select(TodoModel.version_id, TodoModel.status, func.count())
            .where(TodoModel.version_id.in_(version_ids))
            .group_by(TodoModel.version_id, TodoModel.status)
        )
        stats: dict[uuid.UUID, dict[str, int]] = {vid: {} for vid in version_ids}
        for vid, status, count in result.all():
            stats[vid][status] = count
        return stats

    async def count_by_project(self, project_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(VersionModel)
            .where(VersionModel.project_id == project_id)
        )
        return result.scalar_one()

    async def delete(self, version_id: uuid.UUID) -> bool:
        result = await self.db.execute(select(VersionModel).where(VersionModel.id == version_id))
        model = result.scalar_one_or_none()
        if not model:
            return False
        await self.db.delete(model)
        await self.db.flush()
        return True

    @staticmethod
    def _to_entity(model: VersionModel) -> Version:
        return Version(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            goal=model.goal or "",
            status=VersionStatus(model.status),
            parent_version_id=model.parent_version_id,
            order=model.order or 0,
            changelog=model.changelog or "",
            prototype_preview_url=model.prototype_preview_url or "",
            deploy_url=model.deploy_url or "",
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
