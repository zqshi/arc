from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, UploadFile, File

from arc.application.project.service import VersionService
from arc.domain.project.entity import Project, Version
from arc.infrastructure.repositories.project import (
    ProjectRepository,
    VersionRepository,
)
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.project import (
    ApplyWithDiffRequest,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    VersionCreate,
    VersionResponse,
    VersionUpdate,
    PlanningSessionCreate,
    PlanningSessionResponse,
    DocumentResponse,
)
from arc.interface.schemas.experience import ExperienceListResponse, ExperienceResponse

import re

router = APIRouter()


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


def _project_resp(p: Project) -> ProjectResponse:
    return ProjectResponse(
        id=str(p.id),
        name=p.name,
        description=p.description,
        tech_stack=p.tech_stack,
        repo_url=p.repo_url,
        local_path=p.local_path,
        conventions=p.conventions,
        codebase_summary=p.codebase_summary,
        scan_fingerprint=p.scan_fingerprint,
        status=p.status.value,
        execution_mode=p.execution_mode.value,
        pipeline_config=p.pipeline_config,
        conversation_config=p.conversation_config,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


def _version_resp(v: Version, todo_stats: dict[str, int] | None = None) -> VersionResponse:
    stats = None
    if todo_stats is not None:
        stats = {
            "pending": todo_stats.get("pending", 0),
            "active": todo_stats.get("active", 0),
            "done": todo_stats.get("done", 0),
            "error": todo_stats.get("error", 0),
            "total": sum(todo_stats.values()),
        }
    return VersionResponse(
        id=str(v.id),
        project_id=str(v.project_id),
        name=v.name,
        goal=v.goal,
        status=v.status.value,
        parent_version_id=str(v.parent_version_id) if v.parent_version_id else None,
        order=v.order,
        changelog=v.changelog,
        todo_stats=stats,
        created_at=v.created_at.isoformat(),
        updated_at=v.updated_at.isoformat(),
    )


# ── Projects ──────────────────────────────────────────────


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: DbSession,
    user: CurrentUser,
    include_archived: bool = False,
):
    repo = ProjectRepository(db)
    projects = await repo.list_all(include_archived=include_archived, user_id=user.id)
    return [_project_resp(p) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: DbSession,
    user: CurrentUser,
):
    from arc.domain.project.value_objects import ExecutionMode
    project = Project(
        name=body.name,
        description=body.description,
        tech_stack=body.tech_stack,
        repo_url=body.repo_url,
        conventions=body.conventions,
        execution_mode=ExecutionMode(body.execution_mode),
    )
    repo = ProjectRepository(db)
    await repo.create(project, user_id=user.id)
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
    import asyncio
    import json

    from starlette.responses import StreamingResponse

    from arc.application.project.scan_task import scan_manager

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    pid = str(project_id)

    async def event_generator():
        keepalive_interval = 15

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
            results.append({
                "todo_id": tid,
                "status": "started",
                "conversation_id": str(conv.id),
            })
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
    import asyncio
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


@router.get("/{project_id}/mode-switch-impact")
async def mode_switch_impact(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.todo import TodoRepository
    repo = TodoRepository(db)
    active_todos, _ = await repo.list_all(project_id=project_id, limit=1000)
    active_count = sum(1 for t in active_todos if t.status.value == "active")
    pending_count = sum(1 for t in active_todos if t.status.value == "pending")
    return {
        "active_count": active_count,
        "pending_count": pending_count,
        "safe_to_switch": active_count == 0,
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    version_repo = VersionRepository(db)
    count = await version_repo.count_by_project(project_id)
    if count > 0:
        raise HTTPException(409, "请先删除所有版本后再删除项目")
    await repo.delete(project_id)


@router.get("/{project_id}/dashboard")
async def project_dashboard(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from sqlalchemy import func, select

    from arc.infrastructure.models.agent import AgentSessionModel
    from arc.infrastructure.models.todo import Todo as TodoModel

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    version_repo = VersionRepository(db)
    versions = await version_repo.list_by_project(project_id)
    all_stats = await version_repo.batch_count_todos_by_status([v.id for v in versions])

    version_progress = []
    for v in versions:
        stats = all_stats.get(v.id, {})
        total = sum(stats.values())
        done = stats.get("done", 0)
        version_progress.append({
            "id": str(v.id),
            "name": v.name,
            "status": v.status.value,
            "total": total,
            "done": done,
            "progress": round(done / total * 100, 1) if total else 0,
        })

    todo_result = await db.execute(
        select(TodoModel.status, func.count())
        .where(TodoModel.project_id == project_id)
        .group_by(TodoModel.status)
    )
    todo_stats = {row[0]: row[1] for row in todo_result.all()}

    agent_result = await db.execute(
        select(AgentSessionModel.status, func.count())
        .where(AgentSessionModel.todo_id.in_(
            select(TodoModel.id).where(TodoModel.project_id == project_id)
        ))
        .group_by(AgentSessionModel.status)
    )
    agent_stats = {row[0]: row[1] for row in agent_result.all()}

    recent_result = await db.execute(
        select(TodoModel)
        .where(TodoModel.project_id == project_id)
        .order_by(TodoModel.updated_at.desc())
        .limit(5)
    )
    recent_todos = [
        {
            "id": str(t.id),
            "title": t.title,
            "status": t.status,
            "updated_at": t.updated_at.isoformat(),
        }
        for t in recent_result.scalars().all()
    ]

    return {
        "project_id": str(project_id),
        "todo_stats": {
            "pending": todo_stats.get("pending", 0),
            "active": todo_stats.get("active", 0),
            "done": todo_stats.get("done", 0),
            "error": todo_stats.get("error", 0),
            "total": sum(todo_stats.values()),
        },
        "version_progress": version_progress,
        "agent_stats": {
            "pending": agent_stats.get("pending", 0),
            "running": agent_stats.get("running", 0),
            "completed": agent_stats.get("completed", 0),
            "error": agent_stats.get("error", 0),
        },
        "recent_activity": recent_todos,
    }


# ── Versions ──────────────────────────────────────────────


@router.get("/{project_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = VersionRepository(db)
    versions = await repo.list_by_project(project_id)
    all_stats = await repo.batch_count_todos_by_status([v.id for v in versions])
    return [_version_resp(v, all_stats.get(v.id, {})) for v in versions]


@router.post(
    "/{project_id}/versions", response_model=VersionResponse, status_code=201
)
async def create_version(
    project_id: uuid.UUID,
    body: VersionCreate,
    db: DbSession,
    user: CurrentUser,
):
    repo = VersionRepository(db)
    next_order = await repo._next_order(project_id)

    if body.name and body.name.strip():
        name = body.name.strip()
    else:
        all_versions = await repo.list_by_project(project_id)
        name = _next_version_name(all_versions, body.version_type)

    version = Version(
        project_id=project_id,
        name=name,
        goal=body.goal,
        order=next_order,
        parent_version_id=uuid.UUID(body.parent_version_id) if body.parent_version_id else None,
    )
    try:
        await repo.create(version)
    except ValueError as e:
        raise HTTPException(409, str(e))
    stats = await repo.count_todos_by_status(version.id)
    return _version_resp(version, stats)


@router.patch(
    "/{project_id}/versions/{version_id}", response_model=VersionResponse
)
async def update_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    body: VersionUpdate,
    db: DbSession,
    user: CurrentUser,
):
    repo = VersionRepository(db)
    version = await repo.get_by_id(version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(404, "Version not found")

    updates = body.model_dump(exclude_unset=True)
    for key, val in updates.items():
        setattr(version, key, val)
    await repo.update(version)
    stats = await repo.count_todos_by_status(version_id)
    return _version_resp(version, stats)


@router.post(
    "/{project_id}/versions/{version_id}/activate",
    response_model=VersionResponse,
)
async def activate_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    svc = VersionService(db)
    try:
        version = await svc.activate_version(project_id, version_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    stats = await svc.version_repo.count_todos_by_status(version_id)
    return _version_resp(version, stats)


@router.post(
    "/{project_id}/versions/{version_id}/release",
    response_model=VersionResponse,
)
async def release_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    svc = VersionService(db)
    try:
        version, carry_over = await svc.release_version(project_id, version_id)
    except ValueError as e:
        raise HTTPException(409, str(e))

    try:
        from arc.application.planning.planning_service import PlanningService
        planning_svc = PlanningService(db)
        await planning_svc.extract_release_experience(project_id, version_id)
    except Exception:
        pass

    stats = await svc.version_repo.count_todos_by_status(version_id)
    return _version_resp(version, stats)


@router.delete(
    "/{project_id}/versions/{version_id}",
    status_code=204,
)
async def delete_version(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = VersionRepository(db)
    version = await repo.get_by_id(version_id)
    if not version or version.project_id != project_id:
        raise HTTPException(404, "Version not found")
    if version.status.value == "released":
        raise HTTPException(409, "已发布版本不可删除")
    stats = await repo.count_todos_by_status(version_id)
    if sum(stats.values()) > 0:
        raise HTTPException(409, "请先删除版本下的需求后再删除版本")
    await repo.delete(version_id)


# ── Project Experiences ──────────────────────────────────


@router.get("/{project_id}/experiences", response_model=ExperienceListResponse)
async def list_project_experiences(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    status: str | None = None,
    category: str | None = None,
):
    from arc.domain.todo.value_objects import ExperienceCategory, ExperienceStatus
    from arc.infrastructure.repositories.experience import ExperienceRepository

    repo = ExperienceRepository(db)
    st = ExperienceStatus(status) if status and status in ("draft", "confirmed", "archived") else None
    experiences, total = await repo.list_all(project_id=project_id, status=st, user_id=user.id)

    if category:
        try:
            cat = ExperienceCategory(category)
            experiences = [e for e in experiences if e.category == cat]
            total = len(experiences)
        except ValueError:
            pass

    return ExperienceListResponse(
        items=[_exp_resp(e) for e in experiences],
        total=total,
    )


@router.get("/{project_id}/experience-insights")
async def project_experience_insights(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.experience import ExperienceRepository

    repo = ExperienceRepository(db)
    high = await repo.list_high_confidence(project_id)
    return {
        "suggestions": [
            {
                "id": str(e.id),
                "title": e.title,
                "solution": e.solution,
                "confidence": e.confidence,
                "reuse_count": e.reuse_count,
            }
            for e in high
        ]
    }


def _exp_resp(exp) -> ExperienceResponse:
    return ExperienceResponse(
        id=str(exp.id),
        todo_id=str(exp.todo_id) if exp.todo_id else None,
        project_id=str(exp.project_id) if exp.project_id else None,
        version_id=str(exp.version_id) if exp.version_id else None,
        title=exp.title,
        scope=exp.scope.value if hasattr(exp.scope, "value") else str(exp.scope),
        status=exp.status.value if hasattr(exp.status, "value") else str(exp.status),
        category=exp.category.value if hasattr(exp.category, "value") else str(exp.category),
        source=exp.source.value if hasattr(exp.source, "value") else str(exp.source),
        problem=exp.problem,
        solution=exp.solution,
        decisions=exp.decisions,
        pitfalls=exp.pitfalls,
        applicable_scenarios=exp.applicable_scenarios,
        tags=[{"label": t.label, "color": t.color} for t in exp.tags],
        confidence=exp.confidence,
        reuse_count=exp.reuse_count,
        metadata=exp.metadata,
        created_at=exp.created_at,
        updated_at=exp.updated_at,
    )


# ── Documents (规划引擎) ─────────────────────────────────


@router.post("/{project_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    project_id: uuid.UUID,
    file: UploadFile,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.document_service import DocumentService
    svc = DocumentService(db)

    data = await file.read()
    doc = await svc.upload(
        project_id=project_id,
        filename=file.filename or "unknown",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return DocumentResponse(
        id=str(doc.id),
        project_id=str(doc.project_id),
        filename=doc.filename,
        content_type=doc.content_type,
        size=doc.size,
        status=doc.status.value,
        parsed_features=doc.parsed_features,
        created_at=doc.created_at.isoformat(),
    )


@router.get("/{project_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.document_service import DocumentService
    svc = DocumentService(db)
    docs = await svc.list_by_project(project_id)
    return [
        DocumentResponse(
            id=str(d.id),
            project_id=str(d.project_id),
            filename=d.filename,
            content_type=d.content_type,
            size=d.size,
            status=d.status.value,
            parsed_features=d.parsed_features,
            created_at=d.created_at.isoformat(),
        )
        for d in docs
    ]


@router.delete("/{project_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    project_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.document_service import DocumentService
    svc = DocumentService(db)
    await svc.delete(doc_id)


# ── Planning Sessions (版本规划) ──────────────────────────


@router.post(
    "/{project_id}/planning-sessions",
    response_model=PlanningSessionResponse,
    status_code=201,
)
async def create_planning_session(
    project_id: uuid.UUID,
    body: PlanningSessionCreate,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.planning_service import PlanningService
    svc = PlanningService(db)
    session = await svc.create_session(
        project_id=project_id,
        document_ids=[uuid.UUID(d) for d in body.document_ids],
        constraints=body.constraints.model_dump() if body.constraints else None,
        version_id=uuid.UUID(body.version_id) if body.version_id else None,
    )
    return _planning_session_resp(session)


@router.get(
    "/{project_id}/planning-sessions",
    response_model=list[PlanningSessionResponse],
)
async def list_planning_sessions(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.planning import PlanningSessionRepository
    repo = PlanningSessionRepository(db)
    sessions = await repo.list_by_project(project_id)
    return [_planning_session_resp(s) for s in sessions]


@router.post(
    "/{project_id}/planning-sessions/{session_id}/generate",
    response_model=PlanningSessionResponse,
)
async def generate_roadmap(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.planning_service import PlanningService
    svc = PlanningService(db)
    await svc.generate_roadmap(session_id)
    from arc.infrastructure.repositories.planning import PlanningSessionRepository
    repo = PlanningSessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return _planning_session_resp(session)


@router.post(
    "/{project_id}/planning-sessions/{session_id}/confirm",
    response_model=PlanningSessionResponse,
)
async def confirm_roadmap(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.planning import PlanningSessionRepository
    repo = PlanningSessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    session.confirm()
    await repo.update(session)
    return _planning_session_resp(session)


@router.post(
    "/{project_id}/planning-sessions/{session_id}/apply",
)
async def apply_roadmap(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.planning_service import PlanningService
    svc = PlanningService(db)
    versions = await svc.apply_roadmap(session_id)
    return {
        "message": f"已创建 {len(versions)} 个版本",
        "version_ids": [str(v.id) for v in versions],
    }


@router.post(
    "/{project_id}/planning-sessions/{session_id}/preview-diff",
)
async def preview_apply_diff(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.planning_service import PlanningService
    svc = PlanningService(db)
    try:
        diff = await svc.preview_apply_diff(session_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return diff


@router.post(
    "/{project_id}/planning-sessions/{session_id}/apply-with-diff",
)
async def apply_with_diff(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    body: ApplyWithDiffRequest,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.planning_service import PlanningService
    svc = PlanningService(db)
    try:
        result = await svc.apply_with_diff(
            session_id,
            [uuid.UUID(tid) for tid in body.abandon_todo_ids],
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


@router.post(
    "/{project_id}/planning-sessions/{session_id}/revise",
    response_model=PlanningSessionResponse,
)
async def revise_planning_session(
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.planning import PlanningSessionRepository
    repo = PlanningSessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    session.revise()
    await repo.update(session)
    return _planning_session_resp(session)


@router.get(
    "/{project_id}/versions/{version_id}/planning-sessions",
    response_model=list[PlanningSessionResponse],
)
async def list_version_planning_sessions(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.planning import PlanningSessionRepository
    repo = PlanningSessionRepository(db)
    sessions = await repo.list_by_version(version_id)
    return [_planning_session_resp(s) for s in sessions]


@router.post(
    "/{project_id}/versions/{version_id}/analyze",
)
async def analyze_iteration(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.planning_service import PlanningService
    svc = PlanningService(db)
    analysis = await svc.analyze_iteration(project_id, version_id)
    return {"analysis": analysis}


def _planning_session_resp(s) -> PlanningSessionResponse:
    return PlanningSessionResponse(
        id=str(s.id),
        project_id=str(s.project_id),
        version_id=str(s.version_id) if s.version_id else None,
        document_ids=[str(d) for d in s.document_ids],
        constraints=s.constraints,
        roadmap=s.roadmap,
        conversation_id=str(s.conversation_id) if s.conversation_id else None,
        status=s.status.value if hasattr(s.status, "value") else str(s.status),
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )
