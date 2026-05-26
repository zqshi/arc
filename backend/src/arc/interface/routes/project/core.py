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
    from arc.domain.project.value_objects import ExecutionMode
    from arc.infrastructure.repositories.project_member import ProjectMemberRepository

    if org_id:
        from arc.application.billing.quota_service import QuotaService
        await QuotaService(db).check_project_limit(org_id)

    project = Project(
        name=body.name,
        organization_id=org_id,
        description=body.description,
        tech_stack=body.tech_stack,
        repo_url=body.repo_url,
        conventions=body.conventions,
        execution_mode=ExecutionMode(body.execution_mode),
    )
    repo = ProjectRepository(db)
    await repo.create(project, user_id=user.id)

    member_repo = ProjectMemberRepository(db)
    await member_repo.add_member(project.id, user.id, "admin")

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

    if "pipeline_config" in updates and updates["pipeline_config"]:
        project.update_pipeline_config(updates.pop("pipeline_config"))

    if "conversation_config" in updates and updates["conversation_config"]:
        project.update_conversation_config(updates.pop("conversation_config"))

    for key, val in updates.items():
        if val is not None:
            setattr(project, key, val)
    await repo.update(project)
    return _project_resp(project)


@router.post("/{project_id}/scan-codebase")
async def scan_codebase(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    force: bool = False,
):
    from pathlib import Path

    from arc.application.project.scan_task import scan_manager
    from arc.application.project.scanner import compute_scan_fingerprint

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.local_path:
        raise HTTPException(400, "请先配置本地工作目录")

    path = Path(project.local_path).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(400, f"目录不存在: {project.local_path}")

    pid = str(project_id)

    if not force and project.codebase_summary:
        current_fp = await compute_scan_fingerprint(str(path))
        if current_fp == project.scan_fingerprint:
            return {"summary": project.codebase_summary, "cached": True}

    if scan_manager.is_running(pid):
        raise HTTPException(409, "扫描进行中，请勿重复操作")

    task_id = await scan_manager.start_scan(pid, str(path))
    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=202,
        content={"task_id": task_id, "status": "running"},
    )


@router.get("/{project_id}/scan-codebase/stream")
async def scan_codebase_stream(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    import json

    from starlette.responses import StreamingResponse

    from arc.application.project.scan_task import scan_manager

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    pid = str(project_id)

    async def event_generator():
        async for event in scan_manager.subscribe(pid):
            event_type = event.get("event", "message")
            data = json.dumps(event, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

        yield "event: close\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


# ── GitHub Integration ─────────────────────────────────────


@router.post("/{project_id}/github/connect")
async def connect_github(
    project_id: uuid.UUID,
    body: dict,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.integration.github_service import GitHubService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.repo_url:
        raise HTTPException(400, "请先配置代码仓库地址")

    token = body.get("token", "").strip()
    if not token:
        raise HTTPException(400, "token is required")

    svc = GitHubService(db)
    result = await svc.connect(project, token)
    return {
        "status": "connected",
        "repo": result["full_name"],
        "webhook_url": f"/api/webhooks/github/{project_id}",
        "webhook_secret": result["webhook_secret"],
    }


@router.delete("/{project_id}/github/disconnect")
async def disconnect_github(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.integration.github_service import GitHubService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = GitHubService(db)
    await svc.disconnect(project)
    return {"status": "disconnected"}


@router.post("/{project_id}/github/sync")
async def sync_github_issues(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.integration.github_service import GitHubService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.github_token:
        raise HTTPException(400, "GitHub 未连接")

    svc = GitHubService(db)
    results = await svc.sync_issues(project)
    created = sum(1 for r in results if r["action"] == "created")
    updated = sum(1 for r in results if r["action"] == "updated")
    return {"synced": len(results), "created": created, "updated": updated}
