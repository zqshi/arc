"""Project GitHub integration routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from arc.infrastructure.repositories.project import ProjectRepository
from arc.interface.deps import CurrentUser, DbSession

router = APIRouter()


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

    repo_url = body.get("repo_url", "").strip()
    if repo_url:
        project.repo_url = repo_url

    if not project.repo_url:
        raise HTTPException(400, "请先配置代码仓库地址")

    token = body.get("token", "").strip()
    if not token:
        raise HTTPException(400, "token is required")

    svc = GitHubService(db)
    try:
        result = await svc.connect(project, token)
    except Exception:
        await db.rollback()
        raise

    await db.commit()

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


@router.post("/{project_id}/github/clone")
async def clone_github_repo(
    project_id: uuid.UUID,
    body: dict,
    db: DbSession,
    user: CurrentUser,
):
    """Clone the GitHub repo to a local directory and set project.local_path."""
    import subprocess

    from arc.application.integration.github_service import GitHubService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.repo_url:
        raise HTTPException(400, "请先配置代码仓库地址")

    target_path = body.get("path", "").strip() or None

    svc = GitHubService(db)
    try:
        result = await svc.clone_repo(project, target_path)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Git clone 超时，仓库可能过大")
    except RuntimeError as e:
        raise HTTPException(400, f"Clone 失败: {e}")
    except Exception as e:
        raise HTTPException(500, f"Clone 异常: {e}")

    await db.commit()
    return result


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
