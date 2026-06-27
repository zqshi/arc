from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

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
    from arc.application.project.workspace_service import ProjectWorkspaceService

    svc = ProjectWorkspaceService(db)
    try:
        project = await svc.create_project(
            name=body.name,
            user_id=user.id,
            organization_id=org_id,
            description=body.description,
            tech_stack=body.tech_stack,
            repo_url=body.repo_url,
            conventions=body.conventions,
            execution_mode=body.execution_mode,
            process_constraint=body.process_constraint,
            project_type=body.project_type,
            workspace_type=body.workspace_type,
            local_path=body.local_path,
            github_token=body.github_token,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

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
    from arc.application.project.workspace_service import ProjectWorkspaceService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    updates = body.model_dump(exclude_unset=True)
    svc = ProjectWorkspaceService(db)
    project = await svc.apply_project_updates(project, updates)
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
    from arc.application.project.workspace_service import ProjectWorkspaceService

    target_path = (body.get("target_path") or "").strip()
    if not target_path:
        raise HTTPException(400, "target_path is required")

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = ProjectWorkspaceService(db)
    project = await svc.migrate_workspace(project, target_path)

    return _project_resp(project)
