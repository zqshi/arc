from __future__ import annotations

import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from arc.domain.todo.value_objects import TodoStatus
from arc.infrastructure.repositories.todo import TodoDependencyRepository, TodoRepository
from arc.interface.deps import CurrentUser, DbSession
from arc.interface.schemas import (
    AddDependencyRequest,
    ConversationListResponse,
    CreateTodoRequest,
    DependencyListResponse,
    TodoListResponse,
    TodoResponse,
    UpdateTodoRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=TodoListResponse)
async def list_todos(
    db: DbSession,
    user: CurrentUser,
    status: str | None = None,
    project_id: str | None = None,
    version_id: str | None = None,
    page: int = 1,
    page_size: int = Query(default=50, le=200),
):
    repo = TodoRepository(db)
    pid = UUID(project_id) if project_id else None
    vid = UUID(version_id) if version_id else None
    offset = (page - 1) * page_size

    if status and status != "all":
        todos, total = await repo.list_by_status(
            TodoStatus(status), user_id=user.id, offset=offset, limit=page_size
        )
    else:
        todos, total = await repo.list_all(
            project_id=pid, version_id=vid, user_id=user.id, offset=offset, limit=page_size
        )

    proj_names, ver_names = await _resolve_names(db, todos)
    dep_repo = TodoDependencyRepository(db)
    todo_ids = [t.id for t in todos]
    blocked_by_map = await dep_repo.get_map(todo_ids)
    blocks_map = await dep_repo.get_blocks_map(todo_ids)
    return TodoListResponse(
        items=[
            _to_response(
                t,
                project_name=proj_names.get(t.project_id),
                version_name=ver_names.get(t.version_id),
                blocked_by=blocked_by_map.get(t.id, []),
                blocks=blocks_map.get(t.id, []),
            )
            for t in todos
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(todo_id: str, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    await repo.mark_seen(UUID(todo_id))
    await db.commit()

    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    project_name = None
    version_name = None
    if todo.project_id:
        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(db).get_by_id(todo.project_id)
        if project:
            project_name = project.name
    if todo.version_id:
        from arc.infrastructure.repositories.project import VersionRepository

        version = await VersionRepository(db).get_by_id(todo.version_id)
        if version:
            version_name = version.name

    dep_repo = TodoDependencyRepository(db)
    blocked_by = await dep_repo.get_blocked_by(UUID(todo_id))
    blocks = await dep_repo.get_blocks(UUID(todo_id))
    return _to_response(
        todo,
        project_name=project_name,
        version_name=version_name,
        blocked_by=blocked_by,
        blocks=blocks,
    )


@router.get("/{todo_id}/dependencies", response_model=DependencyListResponse)
async def get_dependencies(todo_id: str, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    dep_repo = TodoDependencyRepository(db)
    blocked_by = await dep_repo.get_blocked_by(UUID(todo_id))
    blocks = await dep_repo.get_blocks(UUID(todo_id))
    return DependencyListResponse(
        blocked_by=[str(uid) for uid in blocked_by],
        blocks=[str(uid) for uid in blocks],
    )


@router.post("/{todo_id}/dependencies", status_code=201)
async def add_dependency(todo_id: str, req: AddDependencyRequest, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    dep_on = await repo.get_by_id(UUID(req.depends_on_id), user_id=user.id)
    if not dep_on:
        raise HTTPException(status_code=404, detail="Dependency target not found")
    if todo_id == req.depends_on_id:
        raise HTTPException(status_code=400, detail="Cannot depend on self")
    dep_repo = TodoDependencyRepository(db)
    await dep_repo.add(UUID(todo_id), UUID(req.depends_on_id))
    return {"status": "ok"}


@router.delete("/{todo_id}/dependencies/{depends_on_id}", status_code=204)
async def remove_dependency(todo_id: str, depends_on_id: str, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    dep_repo = TodoDependencyRepository(db)
    removed = await dep_repo.remove(UUID(todo_id), UUID(depends_on_id))
    if not removed:
        raise HTTPException(status_code=404, detail="Dependency not found")


@router.post("", response_model=TodoResponse, status_code=201)
async def create_todo(req: CreateTodoRequest, db: DbSession, user: CurrentUser):
    from arc.domain.project.value_objects import ExecutionMode
    from arc.domain.todo.entity import Todo
    from arc.domain.todo.value_objects import Tag
    from arc.infrastructure.repositories.project import ProjectRepository

    execution_mode = ExecutionMode.PIPELINE
    if req.project_id:
        project = await ProjectRepository(db).get_by_id(UUID(req.project_id))
        if project:
            execution_mode = project.execution_mode
            if project.organization_id:
                from arc.application.billing.quota_service import QuotaService
                await QuotaService(db).check_todo_limit(project.organization_id, project.id)

    todo = Todo(
        title=req.title,
        description=req.description,
        project_id=UUID(req.project_id) if req.project_id else None,
        version_id=UUID(req.version_id) if req.version_id else None,
        priority=req.priority,
        tags=[Tag(label=t.label, color=t.color) for t in req.tags],
        execution_mode=execution_mode,
    )
    repo = TodoRepository(db)
    created = await repo.create(todo, user_id=user.id)
    return _to_response(created)


@router.put("/{todo_id}", response_model=TodoResponse)
async def update_todo(todo_id: str, req: UpdateTodoRequest, db: DbSession, user: CurrentUser):
    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    if req.title is not None:
        todo.title = req.title
    if req.description is not None:
        todo.description = req.description
    if req.priority is not None:
        todo.priority = req.priority
    if req.project_id is not None:
        todo.project_id = UUID(req.project_id) if req.project_id else None
    if req.version_id is not None:
        todo.version_id = UUID(req.version_id) if req.version_id else None
    if req.tags is not None:
        from arc.domain.todo.value_objects import Tag

        todo.tags = [Tag(label=t.label, color=t.color) for t in req.tags]

    updated = await repo.update(todo)
    return _to_response(updated)


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.infrastructure.storage import get_storage

    storage = get_storage()
    await storage.async_delete_prefix(f"previews/{todo_id}")

    repo = TodoRepository(db)
    await repo.delete(UUID(todo_id), user_id=user.id)


@router.post("/{todo_id}/confirm-push")
async def confirm_push(todo_id: str, db: DbSession, user: CurrentUser, body: dict = {}):
    """用户确认后执行 git commit + push。"""
    from arc.application.agent.git_sync import GitSync
    from arc.infrastructure.repositories.project import ProjectRepository

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    if not todo.project_id:
        raise HTTPException(status_code=400, detail="Todo has no project")

    project = await ProjectRepository(db).get_by_id(todo.project_id)
    if not project or not project.local_path:
        raise HTTPException(status_code=400, detail="Project has no local path")

    git = GitSync(project.local_path)
    if not await git.is_git_repo():
        raise HTTPException(status_code=400, detail="Project directory is not a git repo")

    message = body.get("message") or f"feat: {todo.title}"
    branch = body.get("branch") or None

    result = await git.commit_and_push(message=message, branch=branch)

    if not result.success and result.error:
        # Push 失败 — 诊断原因并返回建议
        diagnosis = await git.diagnose_push_failure(result.error)
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "error": result.error,
                "commit_sha": result.commit_sha,
                "diagnosis": diagnosis,
            },
        )

    return {
        "success": result.success,
        "commit_sha": result.commit_sha,
        "branch": result.branch,
        "remote_url": result.remote_url,
        "files_changed": result.files_changed,
    }


@router.post("/{todo_id}/create-pr")
async def create_pull_request(todo_id: str, db: DbSession, user: CurrentUser, body: dict = {}):
    """Git push 完成后创建 GitHub PR。AI 自动生成 PR description。"""
    from arc.application.agent.git_sync import GitSync
    from arc.infrastructure.repositories.project import ProjectRepository

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    if not todo.project_id:
        raise HTTPException(status_code=400, detail="Todo has no project")

    project = await ProjectRepository(db).get_by_id(todo.project_id)
    if not project:
        raise HTTPException(status_code=400, detail="Project not found")
    if not project.github_token:
        raise HTTPException(status_code=400, detail="GitHub 未连接，请先在项目设置中连接")

    config = project.github_config or {}
    owner = config.get("owner", "")
    repo_name = config.get("repo", "")
    if not owner or not repo_name:
        raise HTTPException(status_code=400, detail="GitHub 仓库信息不完整")

    # 获取当前分支和 diff
    git = GitSync(project.local_path)
    _, branch_out, _ = await _run_git_helper(["rev-parse", "--abbrev-ref", "HEAD"], project.local_path)
    head_branch = body.get("branch") or branch_out.strip()
    base_branch = body.get("base") or await git.get_default_branch()

    if head_branch == base_branch:
        raise HTTPException(status_code=400, detail=f"当前分支 {head_branch} 与目标分支相同，请先创建功能分支")

    # 生成 PR title 和 description
    pr_title = body.get("title") or f"feat: {todo.title}"
    pr_body = body.get("body", "")

    if not pr_body:
        # AI 生成 PR description
        pr_body = await _generate_pr_description(db, todo, project, git)

    # 创建 PR
    from arc.infrastructure.github_client import GitHubClient

    client = GitHubClient(project.github_token)
    try:
        pr_data = await client.create_pull_request(
            owner=owner,
            repo=repo_name,
            title=pr_title,
            body=pr_body,
            head=head_branch,
            base=base_branch,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PR 创建失败: {exc}")
    finally:
        await client.close()

    # 记录 PR URL 到 todo
    pr_url = pr_data.get("html_url", "")
    if pr_url:
        todo.github_pr_url = pr_url
        await repo.update(todo)
        await db.commit()

    return {
        "pr_url": pr_url,
        "pr_number": pr_data.get("number"),
        "title": pr_title,
        "head": head_branch,
        "base": base_branch,
    }


async def _generate_pr_description(db, todo, project, git) -> str:
    """使用 AI 生成 PR description。降级为模板。"""
    try:
        changes = await git.detect_changes()
        diff_context = changes.diff_stat or f"{len(changes.files_changed)} files changed"

        from arc.application.ai.adapter_pool import adapter_pool

        prompt = (
            f"为以下代码变更生成一个简洁的 GitHub PR description（中文，Markdown 格式）。\n\n"
            f"## 需求\n{todo.title}\n{todo.description or ''}\n\n"
            f"## 变更摘要\n{diff_context}\n\n"
            f"## 变更文件\n{chr(10).join(changes.files_changed[:20])}\n\n"
            f"要求：\n"
            f"- 第一段简述本次变更做了什么\n"
            f"- 列出主要改动点（3-5条）\n"
            f"- 如有破坏性变更需标注\n"
            f"- 末尾加 '🤖 Generated by Arc' 标记"
        )

        from arc.application.ai.llm_adapter import LLMMessage

        async with adapter_pool.acquire() as adapter:
            response = await adapter.chat([
                LLMMessage(role="system", content="你是一个专业的 PR reviewer。输出简洁的 PR description。"),
                LLMMessage(role="user", content=prompt),
            ])
            return response.content

    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("AI PR description generation failed: %s", exc)
        # 降级为模板
        return (
            f"## {todo.title}\n\n"
            f"{todo.description or '无描述'}\n\n"
            f"---\n🤖 Generated by Arc"
        )


async def _run_git_helper(args, cwd):
    """Thin wrapper for routes that need one-off git commands."""
    from arc.application.agent.git_sync import _run_git
    return await _run_git(args, cwd)

@router.post("/{todo_id}/extract-tags", response_model=TodoResponse)
async def extract_tags(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.application.todo.service import TodoService

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    svc = TodoService(db)
    todo = await svc.extract_tags(UUID(todo_id))
    return _to_response(todo)


@router.get("/{todo_id}/conversations", response_model=ConversationListResponse)
async def list_todo_conversations(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.infrastructure.repositories.conversation import ConversationRepository
    from arc.interface.routes.conversation import _to_response as conv_to_response

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    conv_repo = ConversationRepository(db)
    conversations = await conv_repo.list_by_todo_id(UUID(todo_id))
    return ConversationListResponse(
        items=[conv_to_response(c) for c in conversations],
        total=len(conversations),
    )


@router.post("/{todo_id}/start-conversation", response_model=TodoResponse)
async def start_conversation(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.application.execution.conversation_strategy import ConversationExecutionService

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    if todo.execution_mode.value != "conversation":
        raise HTTPException(status_code=400, detail="此需求不是对话模式")

    svc = ConversationExecutionService(db)
    _, _ = await svc.initialize(UUID(todo_id))
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    return _to_response(todo)


@router.get("/{todo_id}/deliverables")
async def get_deliverables(todo_id: str, db: DbSession, user: CurrentUser):
    from arc.application.execution.conversation_strategy import ConversationExecutionService

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    svc = ConversationExecutionService(db)
    state = await svc.get_tracker_state(UUID(todo_id))
    return state


@router.post("/{todo_id}/quick-message")
async def send_quick_message(todo_id: str, db: DbSession, user: CurrentUser, body: dict):
    import asyncio

    from arc.application.todo.quick_message_service import run_ai_response
    from arc.domain.todo.value_objects import MessageRole
    from arc.infrastructure.repositories.conversation import ConversationRepository

    repo = TodoRepository(db)
    todo = await repo.get_by_id(UUID(todo_id), user_id=user.id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")

    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required")

    conv_repo = ConversationRepository(db)
    conversations = await conv_repo.list_by_todo_id(UUID(todo_id))
    conv = next((c for c in conversations if c.purpose.value == "unified"), None)
    if not conv:
        raise HTTPException(status_code=404, detail="No active conversation for this todo")

    user_msg = conv.add_message(role=MessageRole.USER, content=content)
    await conv_repo.add_message(conv.id, user_msg)
    await db.commit()

    project_id = str(todo.project_id) if todo.project_id else None

    def _on_ai_done(t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception():
            logger.error("Background AI task failed: %s", t.exception())

    task = asyncio.create_task(
        run_ai_response(
            conversation_id=conv.id,
            todo_id=todo_id,
            project_id=project_id,
        )
    )
    task.add_done_callback(_on_ai_done)

    return {
        "message_id": str(user_msg.id),
        "status": "accepted",
    }


def _to_response(
    todo,
    *,
    project_name: str | None = None,
    version_name: str | None = None,
    blocked_by: list[uuid.UUID] | None = None,
    blocks: list[uuid.UUID] | None = None,
) -> TodoResponse:
    needs_attention = todo.status.value in ("active", "error") and (
        todo.last_seen_at is None or todo.updated_at > todo.last_seen_at
    )
    return TodoResponse(
        id=str(todo.id),
        title=todo.title,
        description=todo.description,
        status=todo.status.value,
        project_id=str(todo.project_id) if todo.project_id else None,
        version_id=str(todo.version_id) if todo.version_id else None,
        project_name=project_name,
        version_name=version_name,
        priority=todo.priority,
        current_phase=todo.current_phase.value if todo.current_phase else None,
        execution_mode=todo.execution_mode.value,
        needs_attention=needs_attention,
        tags=[{"label": t.label, "color": t.color} for t in todo.tags],
        blocked_by=[str(uid) for uid in (blocked_by or [])],
        blocks=[str(uid) for uid in (blocks or [])],
        created_at=todo.created_at,
        updated_at=todo.updated_at,
    )


async def _resolve_names(db, todos) -> tuple[dict, dict]:
    from sqlalchemy import select

    from arc.infrastructure.models.project import ProjectModel, VersionModel

    proj_ids = {t.project_id for t in todos if t.project_id}
    ver_ids = {t.version_id for t in todos if t.version_id}

    proj_names: dict = {}
    ver_names: dict = {}

    if proj_ids:
        result = await db.execute(
            select(ProjectModel.id, ProjectModel.name).where(ProjectModel.id.in_(proj_ids))
        )
        proj_names = {row[0]: row[1] for row in result.all()}

    if ver_ids:
        result = await db.execute(
            select(VersionModel.id, VersionModel.name).where(VersionModel.id.in_(ver_ids))
        )
        ver_names = {row[0]: row[1] for row in result.all()}

    return proj_names, ver_names
