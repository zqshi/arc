from __future__ import annotations

import hashlib
import hmac
import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.project.entity import Project
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import TodoStatus
from arc.infrastructure.github_client import GitHubClient
from arc.infrastructure.repositories.project import ProjectRepository
from arc.infrastructure.repositories.todo import TodoRepository

logger = logging.getLogger(__name__)


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def parse_repo_url(url: str) -> tuple[str, str] | None:
    patterns = [
        r"github\.com[:/]([^/]+)/([^/.]+?)(?:\.git)?$",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1), m.group(2)
    return None


class GitHubService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.todo_repo = TodoRepository(db)

    async def connect(self, project: Project, token: str) -> dict:
        parsed = parse_repo_url(project.repo_url)
        if not parsed:
            from arc.domain.errors import AppError
            raise AppError("无法解析 GitHub 仓库地址，请确认 repo_url 格式", status_code=400)

        owner, repo = parsed
        client = GitHubClient(token)
        try:
            repo_info = await client.get_repo(owner, repo)
        except Exception as exc:
            from arc.domain.errors import AppError
            raise AppError(f"GitHub 连接失败: {exc}", status_code=400)
        finally:
            await client.close()

        webhook_secret = uuid.uuid4().hex
        project.configure_github(token, owner, repo, webhook_secret)
        await self.project_repo.update(project)

        return {
            "owner": owner,
            "repo": repo,
            "full_name": repo_info.get("full_name", f"{owner}/{repo}"),
            "webhook_secret": webhook_secret,
        }

    async def disconnect(self, project: Project) -> None:
        project.disconnect_github()
        await self.project_repo.update(project)

    async def sync_issues(self, project: Project) -> list[dict]:
        config = project.github_config
        if not config or not project.github_token:
            return []

        owner, repo = config["owner"], config["repo"]
        client = GitHubClient(project.github_token)
        try:
            issues = await client.list_issues(owner, repo, state="open")
        finally:
            await client.close()


        results = []
        for issue in issues:
            existing = await self.todo_repo.find_by_github_issue(
                project.id, issue.number
            )
            if existing:
                if existing.title != issue.title or existing.description != issue.body:
                    existing.title = issue.title
                    existing.description = issue.body
                    await self.todo_repo.update(existing)
                    results.append({"issue": issue.number, "action": "updated"})
                else:
                    results.append({"issue": issue.number, "action": "skipped"})
                continue

            todo = Todo(
                title=issue.title,
                description=issue.body,
                project_id=project.id,
                execution_mode=project.execution_mode,
                github_issue_number=issue.number,
            )
            await self.todo_repo.create(todo)
            results.append({"issue": issue.number, "action": "created", "todo_id": str(todo.id)})

        return results

    async def handle_issue_webhook(self, project: Project, payload: dict) -> dict | None:
        action = payload.get("action")
        issue = payload.get("issue", {})
        issue_number = issue.get("number")

        if not issue_number:
            return None

        if action in ("opened", "reopened"):
            existing = await self.todo_repo.find_by_github_issue(
                project.id, issue_number
            )
            if existing:
                return {"action": "exists", "todo_id": str(existing.id)}

            todo = Todo(
                title=issue["title"],
                description=issue.get("body") or "",
                project_id=project.id,
                execution_mode=project.execution_mode,
                github_issue_number=issue_number,
            )
            await self.todo_repo.create(todo)
            return {"action": "created", "todo_id": str(todo.id)}

        elif action == "edited":
            existing = await self.todo_repo.find_by_github_issue(
                project.id, issue_number
            )
            if existing:
                existing.title = issue["title"]
                existing.description = issue.get("body") or ""
                await self.todo_repo.update(existing)
                return {"action": "updated", "todo_id": str(existing.id)}

        elif action == "closed":
            existing = await self.todo_repo.find_by_github_issue(
                project.id, issue_number
            )
            if existing and existing.status not in (TodoStatus.DONE, TodoStatus.ABANDONED):
                existing.complete()
                await self.todo_repo.update(existing)
                return {"action": "completed", "todo_id": str(existing.id)}

        return None

    async def notify_issue_complete(self, todo: Todo, project: Project) -> None:
        if not todo.github_issue_number or not project.github_token:
            return

        config = project.github_config
        if not config:
            return

        owner, repo = config["owner"], config["repo"]
        body = (
            f"**Arc 已完成此需求** :white_check_mark:\n\n"
            f"需求「{todo.title}」已通过 Arc 工作台完成全部交付。"
        )
        if todo.github_pr_url:
            body += f"\n\n关联 PR: {todo.github_pr_url}"

        client = GitHubClient(project.github_token)
        try:
            await client.create_issue_comment(owner, repo, todo.github_issue_number, body)
        except Exception as exc:
            logger.warning("Failed to comment on issue #%d: %s", todo.github_issue_number, exc)
        finally:
            await client.close()
