"""Todo Git operations — confirm-push, create-pr."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException

from arc.infrastructure.repositories.todo import TodoRepository
from arc.interface.deps import CurrentUser, DbSession

logger = logging.getLogger(__name__)

router = APIRouter()


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

    git = GitSync(project.local_path)
    _, branch_out, _ = await _run_git_helper(
        ["rev-parse", "--abbrev-ref", "HEAD"], project.local_path,
    )
    head_branch = body.get("branch") or branch_out.strip()
    base_branch = body.get("base") or await git.get_default_branch()

    if head_branch == base_branch:
        raise HTTPException(
            status_code=400,
            detail=f"当前分支 {head_branch} 与目标分支相同，请先创建功能分支",
        )

    pr_title = body.get("title") or f"feat: {todo.title}"
    pr_body = body.get("body", "")

    if not pr_body:
        pr_body = await _generate_pr_description(db, todo, project, git)

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
        from arc.application.ai.llm_adapter import LLMMessage

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

        async with adapter_pool.acquire() as adapter:
            response = await adapter.chat([
                LLMMessage(
                    role="system",
                    content="你是一个专业的 PR reviewer。输出简洁的 PR description。",
                ),
                LLMMessage(role="user", content=prompt),
            ])
            return response.content

    except Exception as exc:
        logger.warning("AI PR description generation failed: %s", exc)
        return (
            f"## {todo.title}\n\n"
            f"{todo.description or '无描述'}\n\n"
            f"---\n🤖 Generated by Arc"
        )


async def _run_git_helper(args, cwd):
    from arc.application.agent.git_sync import _run_git
    return await _run_git(args, cwd)
