from __future__ import annotations

from arc.domain.project.entity import Project, Version
from arc.interface.schemas.project import ProjectResponse, VersionResponse


def _project_resp(p: Project) -> ProjectResponse:
    gh_config = p.github_config or {}
    gh_connected = bool(p.github_token and gh_config.get("owner"))
    gh_repo = f"{gh_config['owner']}/{gh_config['repo']}" if gh_connected else None
    return ProjectResponse(
        id=str(p.id),
        name=p.name,
        description=p.description,
        tech_stack=p.tech_stack,
        repo_url=p.repo_url,
        local_path=p.local_path,
        conventions=p.conventions,
        codebase_summary=p.codebase_summary,
        scan_fingerprint=p.scan_fingerprint,
        scan_status=p.scan_status,
        scan_progress=p.scan_progress,
        scan_error=p.scan_error,
        status=p.status.value,
        execution_mode=p.execution_mode.value,
        process_constraint=p.process_constraint.value,
        project_type=p.project_type.value,
        process_config=p.process_config.to_dict() if p.process_config else None,
        pipeline_config=p.pipeline_config,
        conversation_config=p.conversation_config,
        github_connected=gh_connected,
        github_repo=gh_repo,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


def _version_resp(v: Version, todo_stats: dict[str, int] | None = None, has_analysis: bool = False, analysis_stale: bool = False) -> VersionResponse:
    stats = None
    if todo_stats is not None:
        stats = {
            "pending": todo_stats.get("pending", 0),
            "active": todo_stats.get("active", 0),
            "done": todo_stats.get("done", 0),
            "error": todo_stats.get("error", 0),
            "total": sum(todo_stats.values()),
        }
    return VersionResponse(
        id=str(v.id),
        project_id=str(v.project_id),
        name=v.name,
        goal=v.goal,
        status=v.status.value,
        parent_version_id=str(v.parent_version_id) if v.parent_version_id else None,
        order=v.order,
        changelog=v.changelog,
        prototype_preview_url=v.prototype_preview_url,
        todo_stats=stats,
        has_analysis=has_analysis,
        analysis_stale=analysis_stale,
        created_at=v.created_at.isoformat(),
        updated_at=v.updated_at.isoformat(),
    )
