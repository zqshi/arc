"""项目工作区管理 — 创建/迁移/clone 编排逻辑。"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.capability.service import CapabilityService
from arc.application.project.convention_templates import ConventionTemplateRegistry
from arc.application.project.governance_writer import GovernanceArtifactWriter
from arc.domain.errors import AppError, ConflictError, NotFoundError
from arc.domain.project.charter import ConventionTemplateProvider
from arc.domain.project.entity import Project
from arc.domain.project.value_objects import (
    ExecutionMode,
    ProcessConfig,
    ProcessConstraint,
    ProjectType,
)
from arc.infrastructure.repositories.project import ProjectRepository
from arc.infrastructure.repositories.project_member import ProjectMemberRepository

logger = logging.getLogger(__name__)


class ProjectWorkspaceService:
    """编排项目创建时的工作区策略分发和后台任务调度。"""

    def __init__(
        self,
        db: AsyncSession,
        template_provider: ConventionTemplateProvider | None = None,
    ):
        self._db = db
        self._project_repo = ProjectRepository(db)
        self._member_repo = ProjectMemberRepository(db)
        # v6.3.0 — 规范模板提供者 (T2 默认 ConventionTemplateRegistry 按类型特化;
        # 可注入自定义 provider 覆盖, 如测试用 stub)
        self._template_provider = template_provider or ConventionTemplateRegistry()

    async def create_project(
        self,
        *,
        name: str,
        user_id: uuid.UUID,
        organization_id: uuid.UUID | None = None,
        description: str = "",
        tech_stack: str = "",
        repo_url: str = "",
        conventions: str = "",
        execution_mode: str = "conversation",
        process_constraint: str | None = None,
        project_type: str | None = None,
        build_target: str | None = None,
        workspace_type: str | None = None,
        local_path: str | None = None,
        github_token: str | None = None,
    ) -> Project:
        """创建项目并处理工作区策略。

        包含：配额检查后的实体构造、工作区策略分发、
        成员初始化、后台 clone/scan 任务调度。
        """
        if organization_id:
            from arc.application.billing.quota_service import QuotaService
            await QuotaService(self._db).check_project_limit(organization_id)

        # 解析约束和执行模式
        constraint = ProcessConstraint(process_constraint) if process_constraint else None
        exec_mode = ExecutionMode(execution_mode)

        if not constraint:
            constraint = (
                ProcessConstraint.STRICT if exec_mode == ExecutionMode.PIPELINE
                else ProcessConstraint.FREE
            )

        project = Project(
            name=name,
            organization_id=organization_id,
            description=description,
            tech_stack=tech_stack,
            repo_url=repo_url,
            conventions=conventions,
            execution_mode=exec_mode,
            process_constraint=constraint,
            project_type=ProjectType(project_type) if project_type else ProjectType.STATIC_SITE,
            process_config=ProcessConfig.from_execution_mode(exec_mode),
        )

        # v6.12: BINARY_APP 非 tauri_linux 构建目标显式注入 sandbox config。
        # tauri_linux 为默认, 由 policy_resolver.default_sandbox_config 运行时推导, 不需存;
        # web/capacitor_apk 需显式存 sandbox.target 供 policy_resolver 推导对应镜像。
        is_non_default_target = (
            project.project_type == ProjectType.BINARY_APP
            and build_target
            and build_target != "tauri_linux"
        )
        if is_non_default_target:
            # capacitor_apk 构建重 (gradle+jvm+aapt2+dex), 默认 512MB 不足, 需 4GB;
            # web (vite) 走默认内存即可。
            sandbox_cfg: dict = {"mode": "docker", "target": build_target}
            if build_target == "capacitor_apk":
                sandbox_cfg["memory_limit_mb"] = 4096
            project.update_conversation_config({"sandbox": sandbox_cfg})

        # 工作区策略处理
        self._apply_workspace_strategy(
            project,
            workspace_type=workspace_type,
            local_path=local_path,
            repo_url=repo_url,
        )

        # v6.3.0 — 按 project_type 初始化项目宪章 (系统生成的意图驱动治理规范)
        project.initialize_charter(self._template_provider)

        # v6.3.0 T3 — charter 落盘到 local_path (temporary/local 立即生效;
        # github 类型 local_path 为空, write() 静默跳过, 待 clone 后补落盘)
        GovernanceArtifactWriter().write(project)

        await self._project_repo.create(project, user_id=user_id)
        await self._member_repo.add_member(project.id, user_id, "admin")

        # 后台任务调度
        self._schedule_background_tasks(
            project,
            workspace_type=workspace_type,
            repo_url=repo_url,
            github_token=github_token,
        )

        return project

    def _apply_workspace_strategy(
        self,
        project: Project,
        *,
        workspace_type: str | None,
        local_path: str | None,
        repo_url: str,
    ) -> None:
        """根据工作区类型设置 project 的路径和 repo_url。

        Raises:
            ValueError: 当 local 路径不存在时。
        """
        if workspace_type == "local" and local_path:
            resolved = Path(local_path).expanduser().resolve()
            if not resolved.is_dir():
                raise NotFoundError(f"目录不存在: {local_path}")
            project.local_path = str(resolved)
        elif workspace_type == "temporary":
            workspace_dir = Path.home() / ".arc" / "workspaces" / str(project.id)
            workspace_dir.mkdir(parents=True, exist_ok=True)
            project.local_path = str(workspace_dir)
        elif workspace_type == "github" and repo_url:
            project.repo_url = repo_url

    def _schedule_background_tasks(
        self,
        project: Project,
        *,
        workspace_type: str | None,
        repo_url: str | None,
        github_token: str | None,
    ) -> None:
        """调度后台 clone 和 scan 任务（fire-and-forget）。"""
        if workspace_type == "github" and repo_url:
            asyncio.create_task(
                self._background_clone(project.id, github_token)
            )

        if workspace_type == "local" and project.local_path:
            asyncio.create_task(
                self._background_scan(str(project.id), project.local_path)
            )

    async def _background_clone(
        self, project_id: uuid.UUID, github_token: str | None
    ) -> None:
        """后台 GitHub clone 任务。"""
        try:
            from arc.infrastructure.database import async_session_factory

            async with async_session_factory() as clone_db:
                clone_repo = ProjectRepository(clone_db)
                p = await clone_repo.get_by_id(project_id)
                if p:
                    from arc.application.integration.github_service import GitHubService
                    svc = GitHubService(clone_db)
                    if github_token:
                        p.github_token = github_token
                        await clone_repo.update(p)
                    await svc.clone_repo(p)
                    await clone_db.commit()
        except Exception as exc:
            logger.warning(
                "Background clone failed for project %s: %s", project_id, exc
            )

    async def _background_scan(self, project_id: str, local_path: str) -> None:
        """后台代码扫描任务。"""
        try:
            from arc.application.project.scan_task import scan_manager
            await scan_manager.start_scan(project_id, local_path)
        except Exception:
            pass

    async def migrate_workspace(
        self,
        project: Project,
        target_path: str,
    ) -> Project:
        """将临时工作区内容迁移到目标目录。

        Args:
            project: 要迁移的项目实体
            target_path: 目标目录路径

        Returns:
            更新后的项目实体

        Raises:
            ValueError: 当前项目不是临时工作区或路径无效时。
        """
        import shutil

        arc_workspace_prefix = str(Path.home() / ".arc" / "workspaces")
        if not project.local_path or not project.local_path.startswith(arc_workspace_prefix):
            raise AppError("当前项目不是临时工作区，无需迁移")

        source = Path(project.local_path)
        target = Path(target_path).expanduser().resolve()

        target.mkdir(parents=True, exist_ok=True)

        if source.exists():
            for item in source.iterdir():
                dest = target / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
            shutil.rmtree(source, ignore_errors=True)

        project.local_path = str(target)
        await self._project_repo.update(project)
        return project

    async def apply_project_updates(
        self, project: Project, updates: dict
    ) -> Project:
        """将前端传入的更新字段应用到项目实体。

        处理 execution_mode / process_constraint / process_config 之间的同步协调，
        以及 pipeline_config / conversation_config 的更新。
        """
        if "execution_mode" in updates and updates["execution_mode"]:
            project.set_execution_mode(ExecutionMode(updates.pop("execution_mode")))

        if "process_constraint" in updates and updates["process_constraint"]:
            constraint = ProcessConstraint(updates.pop("process_constraint"))
            project.process_constraint = constraint
            project.process_config = ProcessConfig(constraint=constraint)
            if constraint == ProcessConstraint.STRICT:
                project.execution_mode = ExecutionMode.PIPELINE
            else:
                project.execution_mode = ExecutionMode.CONVERSATION

        if "process_config" in updates and updates["process_config"]:
            project.process_config = ProcessConfig.from_dict(updates.pop("process_config"))

        if "pipeline_config" in updates and updates["pipeline_config"]:
            project.update_pipeline_config(updates.pop("pipeline_config"))

        if "conversation_config" in updates and updates["conversation_config"]:
            project.update_conversation_config(updates.pop("conversation_config"))

        for key, val in updates.items():
            if val is not None:
                setattr(project, key, val)

        await self._project_repo.update(project)
        return project

    async def update_phase_capabilities(
        self,
        project_id: uuid.UUID,
        phase: str,
        capability_ids: list[uuid.UUID],
        *,
        user_id: uuid.UUID,
    ) -> Project:
        """更新某环节启用的能力 (v6.8.0 W3)。

        编排: 校验 capability 存在 + active (CapabilityService.list_by_ids) →
        project.update_phase_capabilities (结构性校验 phase, 非法抛 DomainError→400) →
        持久化。route 层零逻辑。
        """
        project = await self._project_repo.get_by_id(project_id, user_id=user_id)
        if not project:
            raise NotFoundError("项目不存在")

        if capability_ids:
            caps = await CapabilityService(self._db).list_by_ids(capability_ids)
            found = {c.id for c in caps}
            missing = [cid for cid in capability_ids if cid not in found]
            if missing:
                raise NotFoundError(f"能力不存在: {missing}")
            inactive = [c.name for c in caps if not c.is_active]
            if inactive:
                raise ConflictError(f"能力已禁用, 不可配置: {inactive}")

        project.update_phase_capabilities(phase, [str(cid) for cid in capability_ids])
        await self._project_repo.update(project)
        return project
