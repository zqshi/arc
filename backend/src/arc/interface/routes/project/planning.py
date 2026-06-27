from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, UploadFile

from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas.project import (
    ApplyWithDiffRequest,
    DocumentResponse,
    PlanningSessionCreate,
    PlanningSessionResponse,
)

router = APIRouter()


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
    page: int = 1,
    page_size: int = Query(default=50, le=200),
):
    from arc.application.planning.document_service import DocumentService

    svc = DocumentService(db)
    skip = (page - 1) * page_size
    docs = await svc.list_by_project(project_id, skip=skip, limit=page_size)
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
    page: int = 1,
    page_size: int = Query(default=50, le=200),
):
    from arc.infrastructure.repositories.planning import PlanningSessionRepository

    repo = PlanningSessionRepository(db)
    skip = (page - 1) * page_size
    sessions = await repo.list_by_project(project_id, skip=skip, limit=page_size)
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
    diff = await svc.preview_apply_diff(session_id)
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
        todo_ids = [uuid.UUID(tid) for tid in body.abandon_todo_ids]
    except ValueError as e:
        raise HTTPException(400, str(e))
    result = await svc.apply_with_diff(session_id, todo_ids)
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
    page: int = 1,
    page_size: int = Query(default=50, le=200),
):
    from arc.infrastructure.repositories.planning import PlanningSessionRepository

    repo = PlanningSessionRepository(db)
    sessions = await repo.list_by_version(version_id)
    offset = (page - 1) * page_size
    return [_planning_session_resp(s) for s in sessions[offset : offset + page_size]]


@router.get(
    "/{project_id}/versions/{version_id}/analysis",
)
async def get_analysis(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """读取已有的分析结果（不触发生成）。"""
    from arc.application.planning.analysis_service import AnalysisService

    svc = AnalysisService(db)
    cached_result = await svc.get_latest(version_id)
    if not cached_result:
        raise HTTPException(404, "暂无分析结果")
    content, suggestions = cached_result
    return {"analysis": content, "cached": True, "suggestions": suggestions}


@router.post(
    "/{project_id}/versions/{version_id}/analyze",
)
async def analyze_iteration(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.planning.analysis_service import AnalysisService

    svc = AnalysisService(db)
    content, cached, suggestions = await svc.analyze_iteration(project_id, version_id)
    return {"analysis": content, "cached": cached, "suggestions": suggestions}


@router.post(
    "/{project_id}/versions/{version_id}/detect-conflicts",
)
async def detect_conflicts(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """T5: 检测版本内需求间的领域模型冲突。"""
    from arc.application.planning.conflict_detector import ConflictDetector
    from arc.infrastructure.repositories.todo import TodoRepository

    todo_repo = TodoRepository(db)
    todos, _ = await todo_repo.list_all(version_id=version_id, limit=200)
    features = [
        {"title": t.title, "description": t.description or ""}
        for t in todos
        if t.status.value not in ("done", "abandoned")
    ]

    detector = ConflictDetector(db)
    result = await detector.detect(project_id, features)
    return result
