from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from arc.domain.project.entity import Project
from arc.infrastructure.repositories.project import ProjectRepository
from arc.interface.deps import CurrentOrgId, CurrentUser, DbSession
from arc.interface.routes.project._helpers import _project_resp
from arc.interface.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter()


# ── Projects ──────────────────────────────────────────────


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: DbSession,
    user: CurrentUser,
    org_id: CurrentOrgId = None,
    include_archived: bool = False,
):
    repo = ProjectRepository(db)
    projects = await repo.list_all(
        include_archived=include_archived, user_id=user.id, organization_id=org_id,
    )
    return [_project_resp(p) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: DbSession,
    user: CurrentUser,
    org_id: CurrentOrgId = None,
):
    from pathlib import Path

    from arc.domain.project.value_objects import ExecutionMode, ProcessConfig, ProcessConstraint
    from arc.infrastructure.repositories.project_member import ProjectMemberRepository

    if org_id:
        from arc.application.billing.quota_service import QuotaService
        await QuotaService(db).check_project_limit(org_id)

    # 新项目优先使用 process_constraint，兼容旧 execution_mode
    constraint = ProcessConstraint(body.process_constraint) if body.process_constraint else None
    exec_mode = ExecutionMode(body.execution_mode)

    if not constraint:
        # 从 execution_mode 推导
        constraint = (
            ProcessConstraint.STRICT if exec_mode == ExecutionMode.PIPELINE
            else ProcessConstraint.FREE
        )

    project = Project(
        name=body.name,
        organization_id=org_id,
        description=body.description,
        tech_stack=body.tech_stack,
        repo_url=body.repo_url,
        conventions=body.conventions,
        execution_mode=exec_mode,
        process_constraint=constraint,
        process_config=ProcessConfig.from_execution_mode(exec_mode),
    )

    # 工作区策略处理
    if body.workspace_type == "local" and body.local_path:
        resolved = Path(body.local_path).expanduser().resolve()
        if not resolved.is_dir():
            raise HTTPException(400, f"目录不存在: {body.local_path}")
        project.local_path = str(resolved)
    elif body.workspace_type == "temporary":
        workspace_dir = Path.home() / ".arc" / "workspaces" / str(project.id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        project.local_path = str(workspace_dir)
    elif body.workspace_type == "github" and body.repo_url:
        # GitHub clone 在创建后异步进行，先记录 repo_url
        project.repo_url = body.repo_url
    # else: no workspace (legacy path)

    repo = ProjectRepository(db)
    await repo.create(project, user_id=user.id)

    member_repo = ProjectMemberRepository(db)
    await member_repo.add_member(project.id, user.id, "admin")

    # GitHub 异步 clone — 创建后启动后台任务
    if body.workspace_type == "github" and body.repo_url:
        import asyncio

        from arc.application.integration.github_service import GitHubService
        github_svc = GitHubService(db)

        async def _background_clone():
            try:
                from arc.infrastructure.database import async_session_factory
                async with async_session_factory() as clone_db:
                    clone_repo = ProjectRepository(clone_db)
                    p = await clone_repo.get_by_id(project.id)
                    if p:
                        svc = GitHubService(clone_db)
                        if body.github_token:
                            p.github_token = body.github_token
                            await clone_repo.update(p)
                        await svc.clone_repo(p)
                        await clone_db.commit()
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Background clone failed for project %s: %s", project.id, exc
                )

        asyncio.create_task(_background_clone())

    # 关联本地目录后自动触发代码扫描
    if body.workspace_type == "local" and project.local_path:
        import asyncio as _asyncio

        async def _background_scan():
            try:
                from arc.application.project.scan_task import scan_manager
                await scan_manager.start_scan(str(project.id), project.local_path)
            except Exception:
                pass

        _asyncio.create_task(_background_scan())

    return _project_resp(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    return _project_resp(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    updates = body.model_dump(exclude_unset=True)

    if "execution_mode" in updates and updates["execution_mode"]:
        from arc.domain.project.value_objects import ExecutionMode

        project.set_execution_mode(ExecutionMode(updates.pop("execution_mode")))

    if "process_constraint" in updates and updates["process_constraint"]:
        from arc.domain.project.value_objects import ProcessConfig, ProcessConstraint

        constraint = ProcessConstraint(updates.pop("process_constraint"))
        project.process_constraint = constraint
        # 同步 process_config 和旧 execution_mode
        project.process_config = ProcessConfig(constraint=constraint)
        if constraint == ProcessConstraint.STRICT:
            project.execution_mode = ExecutionMode.PIPELINE
        else:
            project.execution_mode = ExecutionMode.CONVERSATION

    if "process_config" in updates and updates["process_config"]:
        from arc.domain.project.value_objects import ProcessConfig

        project.process_config = ProcessConfig.from_dict(updates.pop("process_config"))

    if "pipeline_config" in updates and updates["pipeline_config"]:
        project.update_pipeline_config(updates.pop("pipeline_config"))

    if "conversation_config" in updates and updates["conversation_config"]:
        project.update_conversation_config(updates.pop("conversation_config"))

    for key, val in updates.items():
        if val is not None:
            setattr(project, key, val)
    await repo.update(project)
    return _project_resp(project)


@router.post("/{project_id}/batch-start-conversations")
async def batch_start_conversations(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    body: dict,
):
    from arc.application.execution.conversation_strategy import ConversationExecutionService
    from arc.infrastructure.repositories.todo import TodoRepository

    todo_ids = body.get("todo_ids", [])
    if not todo_ids:
        raise HTTPException(400, "todo_ids is required")

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    todo_repo = TodoRepository(db)
    svc = ConversationExecutionService(db)

    results = []
    for tid in todo_ids:
        try:
            todo = await todo_repo.get_by_id(uuid.UUID(tid))
            if not todo or str(todo.project_id) != str(project_id):
                results.append({"todo_id": tid, "status": "error", "detail": "Todo not found"})
                continue
            conv, _ = await svc.initialize(uuid.UUID(tid))
            results.append(
                {
                    "todo_id": tid,
                    "status": "started",
                    "conversation_id": str(conv.id),
                }
            )
        except Exception as e:
            results.append({"todo_id": tid, "status": "error", "detail": str(e)})

    await db.commit()
    return {"results": results}


@router.get("/{project_id}/task-stream")
async def project_task_stream_endpoint(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    import json

    from starlette.responses import StreamingResponse

    from arc.application.project.task_stream import project_task_stream

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    pid = str(project_id)

    async def event_generator():
        yield "event: connected\ndata: {}\n\n"

        async for event in project_task_stream.subscribe(pid):
            event_type = event.pop("event", "message")
            data = json.dumps(event, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{project_id}/archive", response_model=ProjectResponse)
async def archive_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.archive()
    await repo.update(project)
    return _project_resp(project)


@router.post("/{project_id}/activate", response_model=ProjectResponse)
async def activate_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """取消归档，恢复为活跃状态。"""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.activate()
    await repo.update(project)
    return _project_resp(project)


@router.post("/{project_id}/workspace/migrate", response_model=ProjectResponse)
async def migrate_workspace(
    project_id: uuid.UUID,
    body: dict,
    db: DbSession,
    user: CurrentUser,
):
    """将临时工作区内容迁移到目标目录。"""
    import shutil
    from pathlib import Path

    target_path = (body.get("target_path") or "").strip()
    if not target_path:
        raise HTTPException(400, "target_path is required")

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    # 验证当前 local_path 是临时工作区
    arc_workspace_prefix = str(Path.home() / ".arc" / "workspaces")
    if not project.local_path or not project.local_path.startswith(arc_workspace_prefix):
        raise HTTPException(400, "当前项目不是临时工作区，无需迁移")

    source = Path(project.local_path)
    target = Path(target_path).expanduser().resolve()

    # 确保目标目录存在
    target.mkdir(parents=True, exist_ok=True)

    # 迁移文件
    if source.exists():
        for item in source.iterdir():
            dest = target / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
        # 清理临时目录
        shutil.rmtree(source, ignore_errors=True)

    # 更新 project.local_path
    project.local_path = str(target)
    await repo.update(project)
    return _project_resp(project)
