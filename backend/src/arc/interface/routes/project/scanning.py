"""Project scanning routes — codebase scan lifecycle."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse, StreamingResponse

from arc.infrastructure.repositories.project import ProjectRepository
from arc.interface.deps import CurrentUser, DbSession

router = APIRouter()


@router.get("/{project_id}/scan-codebase/status")
async def scan_codebase_status(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """Check if a scan is currently running for this project."""
    from arc.application.project.scan_task import scan_manager

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    pid = str(project_id)
    running = scan_manager.is_running(pid)

    if not running and project.scan_status == "scanning":
        project.scan_status = "idle"
        project.scan_progress = ""
        await repo.update(project)
        await db.commit()

    return {"running": running, "scan_status": project.scan_status}


@router.post("/{project_id}/scan-codebase")
async def scan_codebase(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    force: bool = False,
):
    from pathlib import Path

    from arc.application.llm.service import LLMProviderService
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
        if force:
            # A: 强制重扫 — 取消旧 task (cancel 后 is_running=False, start_scan 能进)
            await scan_manager.cancel(pid)
        else:
            raise HTTPException(409, "扫描进行中，请勿重复操作")

    if project.scan_status == "scanning":
        project.scan_status = "idle"
        project.scan_progress = ""
        await repo.update(project)
        await db.commit()

    # B: 扫描走 DB 凭证 (D1 resolve_from_project, per-user 隔离), None 时 env 兜底
    llm_config = await LLMProviderService(db).resolve_from_project(project, user.id)

    task_id = await scan_manager.start_scan(pid, str(path), llm_config)
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
    from arc.application.project.scan_task import scan_manager

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    pid = str(project_id)

    async def event_generator():
        has_events = False
        async for event in scan_manager.subscribe(pid):
            has_events = True
            event_type = event.get("event", "message")
            data = json.dumps(event, ensure_ascii=False)
            yield f"event: {event_type}\ndata: {data}\n\n"

        if not has_events:
            last_err = scan_manager.get_last_error(pid)
            if last_err:
                err_event = json.dumps(
                    {"event": "error", "detail": last_err}, ensure_ascii=False
                )
                yield f"event: error\ndata: {err_event}\n\n"
            else:
                fresh_project = await repo.get_by_id(project_id, user_id=user.id)
                summary = (fresh_project.codebase_summary if fresh_project else "") or ""
                done_event = json.dumps(
                    {"event": "done", "summary": summary}, ensure_ascii=False
                )
                yield f"event: done\ndata: {done_event}\n\n"

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
