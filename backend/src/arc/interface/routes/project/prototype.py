"""项目原型预览相关路由 — 从 core.py 拆出以控制文件规模。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from arc.infrastructure.repositories.project import ProjectRepository
from arc.interface.deps import CurrentUser, DbSession

router = APIRouter()


def _empty_prototype_page(project_name: str) -> str:
    """无原型时的友好 HTML 错误页。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>暂无原型 — {project_name}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{height:100vh;display:flex;align-items:center;justify-content:center;font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f0f1a;color:#e0e0e0}}
.card{{text-align:center;max-width:400px;padding:48px 32px}}
.icon{{font-size:64px;margin-bottom:24px;opacity:0.5}}
h1{{font-size:18px;font-weight:600;margin-bottom:12px;color:#fff}}
p{{font-size:13px;color:#888;line-height:1.6}}
</style></head><body>
<div class="card">
  <div class="icon">🎨</div>
  <h1>暂无原型页面</h1>
  <p>项目「{project_name}」还没有生成原型。<br>请先完成需求的设计阶段，AI 会自动产出交互原型。</p>
</div>
</body></html>"""


@router.get("/{project_id}/prototype-bundle")
async def get_prototype_bundle(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    todo_id: str | None = None,
    version_id: str | None = None,
):
    """聚合项目/版本下所有原型页面为统一预览。"""
    from arc.application.artifact.prototype_bundle import PrototypeBundleService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = PrototypeBundleService(db)
    current_todo = uuid.UUID(todo_id) if todo_id else None
    vid = uuid.UUID(version_id) if version_id else None
    bundle = await svc.build_bundle(project_id, version_id=vid, current_todo_id=current_todo)

    return {
        "pages": [
            {
                "name": p.name,
                "source_todo_id": p.source_todo_id,
                "source_todo_title": p.source_todo_title,
                "is_new": p.is_new,
            }
            for p in bundle.pages
        ],
        "shell_html": bundle.shell_html,
        "total_pages": bundle.total_pages,
        "new_pages": bundle.new_pages,
    }


@router.post("/{project_id}/prototype-site/persist")
async def persist_prototype_site(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    """将原型聚合站点持久化到项目本地目录。"""
    from arc.application.artifact.prototype_bundle import PrototypeBundleService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")
    if not project.local_path:
        raise HTTPException(400, "项目未关联本地目录")

    svc = PrototypeBundleService(db)
    site_path = await svc.persist_to_project(project_id)
    if not site_path:
        raise HTTPException(404, "没有原型页面可持久化")
    return {"site_path": site_path, "status": "persisted"}


@router.get("/{project_id}/prototype-status")
async def prototype_status(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    version_id: str | None = None,
):
    """检查项目/版本是否有可预览的原型。前端据此控制按钮状态。"""
    from arc.application.artifact.prototype_bundle import PrototypeBundleService
    from arc.infrastructure.repositories.project import VersionRepository

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    # 确定目标版本：显式指定 > 当前 active 版本 > 无版本
    vid: uuid.UUID | None = None
    preview_url: str = ""
    resolved_version_id: str | None = None

    if version_id:
        vid = uuid.UUID(version_id)
    else:
        version_repo = VersionRepository(db)
        versions = await version_repo.list_by_project(project_id)
        for v in versions:
            if v.status.value == "active":
                vid = v.id
                break
        if not vid:
            for v in versions:
                if v.status.value in ("released", "active"):
                    vid = v.id
                    break

    if vid:
        resolved_version_id = str(vid)
        version_repo = VersionRepository(db)
        version = await version_repo.get_by_id(vid)
        if version and version.prototype_preview_url:
            preview_url = version.prototype_preview_url

    svc = PrototypeBundleService(db)
    bundle = await svc.build_bundle(project_id, version_id=vid)

    return {
        "has_prototype": bundle.total_pages > 0,
        "preview_url": preview_url or None,
        "total_pages": bundle.total_pages,
        "version_id": resolved_version_id,
    }


@router.get("/{project_id}/prototype-preview")
async def prototype_preview(
    project_id: uuid.UUID,
    db: DbSession,
    token: str | None = None,
    version_id: str | None = None,
):
    """返回项目原型站点 HTML，供浏览器直接渲染。

    支持 ?token=xxx query param 鉴权（新 tab 打开场景）。
    支持 ?version_id=xxx 指定版本。
    """
    from pathlib import Path
    from uuid import UUID as _UUID

    from starlette.responses import HTMLResponse, RedirectResponse

    from arc.application.artifact.prototype_bundle import PrototypeBundleService
    from arc.infrastructure.repositories.project import VersionRepository

    # 鉴权：从 query token 获取用户
    auth_user_id = None
    if token:
        try:
            from arc.application.auth.jwt import verify_access_token
            from arc.infrastructure.repositories.user import UserRepository
            payload = verify_access_token(token)
            u = await UserRepository(db).get_by_id(_UUID(payload["sub"]))
            if u and u.is_active:
                auth_user_id = u.id
        except Exception:
            pass
    if not auth_user_id:
        raise HTTPException(401, "未提供认证信息")

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=auth_user_id)
    if not project:
        raise HTTPException(404, "Project not found")

    # 解析目标版本
    vid: uuid.UUID | None = None
    if version_id:
        vid = uuid.UUID(version_id)
    else:
        version_repo = VersionRepository(db)
        versions = await version_repo.list_by_project(project_id)
        for v in versions:
            if v.status.value == "active":
                vid = v.id
                break
        if not vid:
            for v in versions:
                if v.status.value == "released":
                    vid = v.id
                    break

    # 优先级 1：版本有 S3 preview URL → redirect
    if vid:
        version_repo = VersionRepository(db)
        version = await version_repo.get_by_id(vid)
        if version and version.prototype_preview_url:
            return RedirectResponse(version.prototype_preview_url)

    # 优先级 2：本地静态文件（legacy 兼容）
    if project.local_path:
        site_file = Path(project.local_path) / ".arc" / "prototype" / "index.html"
        if site_file.exists():
            return HTMLResponse(site_file.read_text(encoding="utf-8"))

    # 优先级 3：动态生成
    svc = PrototypeBundleService(db)
    bundle = await svc.build_bundle(project_id, version_id=vid)
    if bundle.shell_html:
        return HTMLResponse(bundle.shell_html)

    # 404：返回友好 HTML 页面而非裸 JSON
    return HTMLResponse(
        _empty_prototype_page(project.name),
        status_code=404,
    )
