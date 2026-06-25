"""项目原型预览相关路由 — 工程模式下直接 redirect 到部署 URL。"""
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
  <p>项目「{project_name}」还没有生成原型。<br>请先完成需求的设计阶段，\
AI 会自动创建前端工程并部署。</p>
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
    """查询项目/版本原型工程的部署状态和路由表。"""
    from arc.application.artifact.prototype_bundle import PrototypeBundleService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = PrototypeBundleService(db)
    vid = uuid.UUID(version_id) if version_id else None
    bundle = await svc.build_bundle(project_id, version_id=vid)

    return {
        "preview_url": bundle.preview_url,
        "routes": [
            {"path": r.path, "name": r.name, "component": r.component}
            for r in bundle.routes
        ],
        "total_pages": bundle.total_pages,
        "tech_stack": bundle.tech_stack,
        "build_status": bundle.build_status,
    }


@router.get("/{project_id}/prototype-status")
async def prototype_status(
    project_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    version_id: str | None = None,
):
    """检查项目/版本是否有可预览的原型。前端据此控制按钮状态。"""
    from arc.application.artifact.prototype_preview import PrototypePreviewService

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=user.id)
    if not project:
        raise HTTPException(404, "Project not found")

    svc = PrototypePreviewService(db)
    status = await svc.get_prototype_status(project_id, version_id)

    return {
        "has_prototype": status.has_prototype,
        "preview_url": status.preview_url,
        "total_pages": status.total_pages,
        "version_id": status.version_id,
    }


@router.get("/{project_id}/prototype-preview")
async def prototype_preview(
    project_id: uuid.UUID,
    db: DbSession,
    token: str | None = None,
    version_id: str | None = None,
):
    """返回原型预览 — 工程模式下 redirect 到部署 URL。

    支持 ?token=xxx query param 鉴权（新 tab 打开场景）。
    支持 ?version_id=xxx 指定版本。
    """
    from starlette.responses import HTMLResponse, RedirectResponse

    from arc.application.artifact.prototype_preview import PrototypePreviewService

    svc = PrototypePreviewService(db)

    # 鉴权
    auth_user_id = None
    if token:
        auth_user_id = await svc.authenticate_by_token(token)
    if not auth_user_id:
        raise HTTPException(401, "未提供认证信息")

    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id, user_id=auth_user_id)
    if not project:
        raise HTTPException(404, "Project not found")

    result = await svc.get_preview_content(
        project_id, project.local_path, project.name, version_id
    )

    if result.type == "redirect":
        return RedirectResponse(result.content)
    return HTMLResponse(_empty_prototype_page(result.content), status_code=404)
