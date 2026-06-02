from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from arc.infrastructure.models.project import ProjectModel
from arc.infrastructure.repositories.project import (
    ProjectRepository,
    VersionRepository,
)
from arc.interface.deps import CurrentUser, DbSession

router = APIRouter()


# ── Domain Model ────────────────────────────────────────────


@router.get("/{project_id}/domain-model")
async def get_domain_model(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    dm = project.domain_model
    if dm and (dm.get("aggregates") or dm.get("subdomains")):
        return dm

    # Fallback 1: extract from existing tech_architecture artifacts
    from arc.application.execution.domain_model_extractor import DomainModelExtractor
    from arc.infrastructure.repositories.artifact import ArtifactRepository
    from arc.infrastructure.repositories.todo import TodoRepository

    todo_repo = TodoRepository(db)
    art_repo = ArtifactRepository(db)
    todos, _ = await todo_repo.list_all(
        project_id=project_id, user_id=user.id, offset=0, limit=100,
    )
    if todos:
        arts_map = await art_repo.list_by_todo_ids([t.id for t in todos])
        for todo in todos:
            for art in arts_map.get(todo.id, []):
                if art.artifact_type.value == "tech_architecture" and (
                    art.content.get("data_model", {}).get("entities")
                    or art.content.get("domain_design")
                ):
                    extractor = DomainModelExtractor(db)
                    updated = await extractor.extract_and_merge(
                        todo.id, art.content,
                    )
                    if updated:
                        await db.commit()
                        project = await repo.get_by_id(
                            project_id, user_id=user.id,
                        )
                        dm = project.domain_model
                        break
            if dm and (dm.get("aggregates") or dm.get("subdomains")):
                break

    # Return what we have + metadata about available sources
    result = dm or {
        "subdomains": [],
        "contexts": [],
        "aggregates": [],
        "relations": [],
        "aggregate_relations": [],
    }

    # Hint to frontend about available extraction sources
    if not result.get("aggregates") and not result.get("subdomains"):
        result["_hint"] = {
            "has_local_path": bool(project.local_path),
            "has_codebase_summary": bool(project.codebase_summary),
            "has_todos": len(todos) > 0 if todos else False,
        }

    return result


@router.post("/{project_id}/domain-model/refresh")
async def refresh_domain_model(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.application.execution.domain_model_extractor import DomainModelExtractor
    from arc.infrastructure.repositories.artifact import ArtifactRepository
    from arc.infrastructure.repositories.todo import TodoRepository

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    todo_repo = TodoRepository(db)
    art_repo = ArtifactRepository(db)
    extractor = DomainModelExtractor(db)

    todos, _ = await todo_repo.list_all(
        project_id=project_id, user_id=user.id, offset=0, limit=500,
    )
    todo_ids = [t.id for t in todos]
    arts_by_todo = await art_repo.list_by_todo_ids(todo_ids)

    merged = 0
    for todo in todos:
        for art in arts_by_todo.get(todo.id, []):
            if art.artifact_type.value != "tech_architecture":
                continue
            has_model = (
                art.content.get("data_model", {}).get("entities")
                or art.content.get("domain_design")
            )
            if not has_model:
                continue
            updated = await extractor.extract_and_merge(
                todo.id, art.content,
            )
            if updated:
                merged += 1

    await db.commit()
    project = await repo.get_by_id(project_id, user_id=user.id)
    dm = project.domain_model or {
        "subdomains": [], "contexts": [], "aggregates": [],
        "relations": [], "aggregate_relations": [],
    }
    return {"merged": merged, "domain_model": dm}


@router.post("/{project_id}/domain-model/extract-from-code")
async def extract_domain_model_from_code(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """Extract domain model directly from codebase source files."""
    from pathlib import Path

    from arc.application.project.scanner import CodebaseScanner
    from arc.application.project.scanner_analysis import (
        build_domain_model_prompt,
        parse_domain_model_response,
    )

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.local_path:
        raise HTTPException(400, "请先配置本地工作目录")

    path = Path(project.local_path).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(400, f"目录不存在: {project.local_path}")

    # Scan and build prompt
    scanner = CodebaseScanner(str(path))
    data = scanner.full_scan()
    prompt = build_domain_model_prompt(data)
    if not prompt:
        raise HTTPException(400, "未找到可分析的源码文件")

    # Call LLM — no fixed token limit, let model output what it needs
    from arc.application.ai.adapter_pool import adapter_pool
    from arc.application.ai.llm_adapter import LLMMessage

    async with adapter_pool.acquire() as adapter:
        response = await adapter.chat(
            [LLMMessage(role="user", content=prompt)],
            temperature=0.1,
            max_tokens=8192,
        )

    domain_model = parse_domain_model_response(response.content)
    if not domain_model:
        raise HTTPException(500, "领域模型提取失败：AI 返回格式无法解析")

    # Merge into existing model
    from datetime import UTC, datetime

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

    await repo.update(project)
    await db.commit()

    return {"domain_model": project.domain_model}


@router.post("/{project_id}/domain-model/validate")
async def validate_domain_model_route(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    dm = project.domain_model or {}

    from arc.application.review.service import ReviewService
    from arc.infrastructure.repositories.review import ReviewFeedbackRepository

    feedback_repo = ReviewFeedbackRepository(db)
    svc = ReviewService(feedback_repo)
    feedbacks, result = await svc.validate_and_persist(project_id, dm)

    result["feedbacks_created"] = len(feedbacks)
    result["reviewed_model_version"] = dm.get("version", 0)
    return result


@router.put("/{project_id}/domain-model")
async def update_domain_model(
    project_id: uuid.UUID,
    body: dict,
    db: DbSession,
    user: CurrentUser,
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.domain_model = body
    project.updated_at = datetime.now(UTC)
    await repo.update(project)
    return project.domain_model


# ── Mode Switch & Delete ──────────────────────────────────


@router.get("/{project_id}/mode-switch-impact")
async def mode_switch_impact(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    from arc.infrastructure.repositories.todo import TodoRepository

    repo = TodoRepository(db)
    active_todos, _ = await repo.list_all(project_id=project_id, user_id=user.id, limit=1000)
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

    # 逻辑删除：标记 status=deleted + deleted_at，保留数据
    project.soft_delete()
    await repo.update(project)
    await db.commit()


@router.post("/{project_id}/restore")
async def restore_project(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """恢复逻辑删除的项目。"""
    repo = ProjectRepository(db)
    # 查询时需包含已删除项目
    result = await db.execute(
        select(ProjectModel).where(ProjectModel.id == project_id)
    )
    model = result.scalar_one_or_none()
    if not model or model.status != "deleted":
        raise HTTPException(404, "Deleted project not found")
    project = repo._to_entity(model)
    project.restore()
    await repo.update(project)
    await db.commit()
    from arc.interface.routes.project._helpers import _project_resp
    return _project_resp(project)
