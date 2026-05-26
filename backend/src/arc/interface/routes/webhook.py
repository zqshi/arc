from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from arc.application.integration.github_service import GitHubService, verify_webhook_signature
from arc.infrastructure.database import async_session_factory
from arc.infrastructure.repositories.project import ProjectRepository

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/github/{project_id}")
async def github_webhook(project_id: UUID, request: Request):
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()

    async with async_session_factory() as db:
        project = await ProjectRepository(db).get_by_id(project_id)
        if not project or not project.github_webhook_secret:
            raise HTTPException(404, "Project not found or GitHub not configured")

        if not verify_webhook_signature(body, signature, project.github_webhook_secret):
            raise HTTPException(401, "Invalid signature")

        event_type = request.headers.get("X-GitHub-Event", "")
        if event_type == "ping":
            return {"status": "pong"}

        if event_type != "issues":
            return {"status": "ignored", "event": event_type}

        import json
        payload = json.loads(body)

        svc = GitHubService(db)
        result = svc.handle_issue_webhook(project, payload)
        import asyncio
        if asyncio.iscoroutine(result):
            result = await result

        await db.commit()
        return {"status": "ok", "result": result}
