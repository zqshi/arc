"""Pipeline 阶段确认后的辅助 hook (v5.8.0 从 pipeline/service.py 拆分)。

各阶段确认后触发的副作用:
- experience 提取 / github 通知 / 经验置信度反馈
- 领域模型合并 / 部署触发 / 前置产出物收集

失败均 graceful (warning, 不阻断 pipeline 主流程)。
"""
from __future__ import annotations

import logging
import uuid

from arc.domain.pipeline.value_objects import PHASE_ORDER, PhaseType

logger = logging.getLogger(__name__)


async def extract_experience(db, todo) -> None:
    """需求完成后提取经验。"""
    from arc.application.experience.service import ExperienceService

    try:
        await ExperienceService(db).extract_from_todo(todo)
    except Exception as exc:
        logger.warning("Experience extraction failed for todo %s: %s", todo.id, exc)


async def notify_github(db, todo) -> None:
    """通知 GitHub issue 完成 (若关联)。"""
    if not todo.github_issue_number or not todo.project_id:
        return
    try:
        from arc.application.integration.github_service import GitHubService
        from arc.infrastructure.repositories.project import ProjectRepository

        project = await ProjectRepository(db).get_by_id(todo.project_id)
        if project and project.github_token:
            await GitHubService(db).notify_issue_complete(todo, project)
    except Exception as exc:
        logger.warning("GitHub notify failed for todo %s: %s", todo.id, exc)


async def feedback_experience_confidence(db, gate_score: int) -> None:
    """根据 gate 分数反馈最近复用经验的置信度。"""
    from arc.infrastructure.repositories.experience import ExperienceRepository

    exp_repo = ExperienceRepository(db)
    try:
        reused = await exp_repo.list_recently_reused(limit=5)
        if not reused:
            return
        normalized = gate_score / 10.0
        for exp in reused:
            old = exp.confidence
            exp.update_confidence(round(old * 0.7 + normalized * 0.3, 3))
            await exp_repo.update(exp)
    except Exception as exc:
        logger.warning("Experience confidence feedback failed: %s", exc)


async def collect_prior_artifacts(
    artifact_repo, todo_id: uuid.UUID, current_phase: PhaseType
) -> dict[str, dict]:
    """收集当前阶段之前已确认的产出物 (交叉一致性检查用)。"""
    from arc.domain.artifact.value_objects import PHASE_ARTIFACT_MAP

    confirmed = await artifact_repo.list_confirmed_by_todo(todo_id)
    result: dict[str, dict] = {}
    for art in confirmed:
        art_phase = None
        for phase, atypes in PHASE_ARTIFACT_MAP.items():
            if art.artifact_type in atypes:
                art_phase = phase
                break
        if art_phase and PHASE_ORDER.get(art_phase, 99) < PHASE_ORDER.get(current_phase, 0):
            result[art.artifact_type.value] = art.content
    return result


async def merge_domain_model(db, todo_id: uuid.UUID, arch_content: dict) -> None:
    """架构确认后自动合并领域模型到项目级 (持续演进)。"""
    from arc.application.execution.domain_model_extractor import DomainModelExtractor

    try:
        extractor = DomainModelExtractor(db)
        updated = await extractor.extract_and_merge(todo_id, arch_content)
        if updated:
            logger.info(
                "Domain model auto-merged from architecture confirmation (todo %s)",
                todo_id,
            )
    except Exception as exc:
        logger.warning("Domain model merge failed for todo %s: %s", todo_id, exc)


async def trigger_deployment(db, todo_repo, todo_id: uuid.UUID, deploy_content: dict) -> None:
    """部署阶段确认后触发真实静态站点部署。

    从 deploy_report.build_evidence / app_code / prototype artifact 读 build_status，
    经 check_build_ready 硬门禁校验后调 DeployService 上传 S3 + 回写 URL。

    build 未就绪 → 抛 BuildGateError (由 confirm_phase 捕获转 PhaseGateError，回滚)，
    杜绝"pipeline 报成功但 deploy_url 为空"的虚假部署。
    部署执行失败 → graceful (warning，基础设施容错，不阻断 pipeline)。
    """
    from pathlib import Path

    from arc.application.deployment.service import DeployService
    from arc.application.execution.build_gate import check_build_ready
    from arc.infrastructure.repositories.project import ProjectRepository

    todo = await todo_repo.get_by_id(todo_id)
    if not todo or not todo.project_id:
        return  # 无项目关联，确实无事可做 (非失败)

    project = await ProjectRepository(db).get_by_id(todo.project_id)
    if not project or not project.local_path:
        logger.info("trigger_deployment: skipped (no local_path) todo=%s", todo_id)
        return  # 无工作区，确实无事可做

    build_status = await _resolve_build_status(db, todo_id, deploy_content)
    artifact_path = deploy_content.get("artifact_path", "dist")
    dist_dir = Path(project.local_path).expanduser() / artifact_path

    # 硬门禁: build 未就绪 → 抛 BuildGateError (confirm_phase 的 begin_nested 回滚)
    check_build_ready(build_status=build_status, dist_dir=dist_dir).ensure_ok()

    try:
        deploy_svc = DeployService(db)
        deployment = await deploy_svc.deploy_static_site(
            project_id=todo.project_id,
            version_id=todo.version_id,
            local_dir=str(dist_dir),
            todo_id=todo_id,
        )
        logger.info(
            "trigger_deployment: completed status=%s url=%s",
            deployment.status.value, deployment.deploy_url,
        )
    except Exception as exc:
        # 部署执行失败 (基础设施问题) 保持 graceful，不阻断 pipeline 主流程
        logger.warning("trigger_deployment failed for todo %s: %s", todo_id, exc)


async def _resolve_build_status(db, todo_id: uuid.UUID, deploy_content: dict) -> str | None:
    """解析 build_status: deploy_report.build_evidence 优先，fallback app_code/prototype artifact。"""
    evidence = deploy_content.get("build_evidence")
    if isinstance(evidence, dict) and evidence.get("build_status"):
        return evidence["build_status"]

    from arc.domain.artifact.value_objects import ArtifactType
    from arc.infrastructure.repositories.artifact import ArtifactRepository

    try:
        arts = await ArtifactRepository(db).list_by_todo_id(todo_id)
        for atype in (ArtifactType.APP_CODE, ArtifactType.PROTOTYPE):
            a = next((x for x in arts if x.artifact_type == atype), None)
            if a and isinstance(a.content, dict) and a.content.get("build_status"):
                return a.content["build_status"]
    except Exception:
        pass
    return deploy_content.get("build_status")
