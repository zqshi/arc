"""从AI对话输出中提取结构化产出物并自动归档。"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.ai.json_extract import extract_json
from arc.application.execution.artifact_post_process import ArtifactPostProcessHooks
from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.planning.entity import DeliverableTracker
from arc.domain.project.value_objects import ProjectType, is_deliverable_visible
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.planning import DeliverableTrackerRepository

if TYPE_CHECKING:
    from arc.application.execution.conversation_gate import ConversationGateResult
    from arc.domain.project.value_objects import ProcessConstraint

logger = logging.getLogger(__name__)

DELIVERABLE_PATTERN = re.compile(
    r"\[DELIVERABLE:([\w_]+)\]\s*```(?:json)?\s*(.*?)^```",
    re.DOTALL | re.MULTILINE,
)


class ArtifactExtractor:
    """从对话模式的AI回复中提取产出物标记，自动创建/更新Artifact并同步DeliverableTracker。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.artifact_repo = ArtifactRepository(db)
        self.tracker_repo = DeliverableTrackerRepository(db)
        # v6.11 T4: 提取后副作用钩子抽离到 ArtifactPostProcessHooks
        # (domain_model提取/BaaS provision/review/experience同步/deliverable范围推断)
        self._hooks = ArtifactPostProcessHooks(db, self.tracker_repo)

    async def process_message(
        self,
        content: str,
        todo_id: uuid.UUID,
    ) -> list[Artifact]:
        """扫描AI回复内容中的 [DELIVERABLE:type] 标记，提取并归档。"""
        matches = DELIVERABLE_PATTERN.findall(content)
        if not matches:
            return []

        extracted: list[Artifact] = []
        tracker = await self.tracker_repo.get_by_todo_id(todo_id)
        constraint = await self._get_constraint(todo_id)
        project_type = await self._get_project_type(todo_id)

        for artifact_type_str, json_str in matches:
            try:
                artifact_type = ArtifactType(artifact_type_str)
            except ValueError:
                logger.warning("Unknown artifact type in DELIVERABLE marker: %s", artifact_type_str)
                continue

            # v6.9: 按项目类型过滤 — 非app类不产出 app_code(无原生构建产物)
            if (
                artifact_type == ArtifactType.APP_CODE
                and project_type is not None
                and not is_deliverable_visible(project_type, ArtifactType.APP_CODE.value)
            ):
                logger.info(
                    "Skip app_code for non-app project %s (type=%s)",
                    todo_id, project_type.value,
                )
                continue

            parsed = extract_json(json_str.strip())
            if not isinstance(parsed, dict):
                try:
                    parsed = json.loads(json_str.strip(), strict=False)
                except (json.JSONDecodeError, ValueError):
                    logger.warning("Failed to parse DELIVERABLE content for %s", artifact_type_str)
                    continue

            artifact = Artifact(
                todo_id=todo_id,
                artifact_type=artifact_type,
                content=parsed,
            )
            saved = await self.artifact_repo.upsert_by_type(artifact)
            extracted.append(saved)

            # 先校验后标记：门禁通过才 PRODUCED，否则 IN_PROGRESS
            # (修复"产出即完成"的虚假状态——产物必须过质量底线门禁才算达标)
            if tracker:
                gate_result = await self._validate_extracted_artifact(
                    saved, todo_id, constraint=constraint,
                )
                if gate_result is not None and gate_result.passed:
                    tracker.mark_produced(artifact_type_str)
                else:
                    tracker.mark_in_progress(artifact_type_str)

        if tracker and extracted:
            await self.tracker_repo.update(tracker)

        for art in extracted:
            if art.artifact_type == ArtifactType.TECH_ARCHITECTURE:
                await self._hooks.try_extract_domain_model(todo_id, art.content)

        # experience_card 产出后，自动同步到 experiences 表
        for art in extracted:
            if art.artifact_type == ArtifactType.EXPERIENCE_CARD:
                await self._hooks.try_sync_experience(todo_id, art.content)

        # requirement_spec 产出后，智能推断适用的交付物范围
        for art in extracted:
            if art.artifact_type == ArtifactType.REQUIREMENT_SPEC and tracker:
                await self._hooks.infer_deliverable_scope(tracker, art.content)

        # prototype 产出后，自动持久化到项目站点目录
        has_prototype = any(a.artifact_type == ArtifactType.PROTOTYPE for a in extracted)
        if has_prototype:
            from arc.application.execution.artifact_deployer import PrototypeDeployer
            deployer = PrototypeDeployer(self.db)
            await deployer.auto_deploy(todo_id)
            # v6.9: 从 prototype content 抽构建产物信息产出 BUILD artifact
            # (BINARY_APP 构建链路锚点, 供④消费侧 deployer/hooks/签名/分发读)
            prototype_art = next(
                (a for a in extracted if a.artifact_type == ArtifactType.PROTOTYPE), None
            )
            if prototype_art:
                await self._try_produce_build_artifact(todo_id, prototype_art)

        return extracted

    async def _get_project_type(self, todo_id: uuid.UUID) -> ProjectType | None:
        """v6.9: 取项目类型(交付物可见性过滤用)。graceful: 失败→None。"""
        try:
            from arc.infrastructure.repositories.project import ProjectRepository
            from arc.infrastructure.repositories.todo import TodoRepository

            todo = await TodoRepository(self.db).get_by_id(todo_id)
            if not todo or not todo.project_id:
                return None
            project = await ProjectRepository(self.db).get_by_id(todo.project_id)
            return project.project_type if project else None
        except Exception:
            return None

    async def _try_produce_build_artifact(
        self, todo_id: uuid.UUID, prototype: Artifact
    ) -> None:
        """v6.9: prototype 提取后, 从 content 抽构建产物信息产出 BUILD artifact。

        仅 BINARY_APP(原生客户端构建链路激活, build_target=tauri_linux)。STATIC_SITE
        走 dist 静态站点部署, 无 build_target/签名/分发, 不产出 BUILD。双读兼容:
        prototype content 仍保留 build_status/artifact_path(④消费改造后废弃)。
        graceful: 取 todo/project 失败或无 build_status → 跳过, 不阻断提取主流程。
        """
        try:
            from arc.application.artifact.service import ArtifactService
            from arc.domain.project.value_objects import ProjectType
            from arc.domain.sandbox.value_objects import BuildTarget
            from arc.infrastructure.repositories.project import ProjectRepository
            from arc.infrastructure.repositories.todo import TodoRepository

            todo = await TodoRepository(self.db).get_by_id(todo_id)
            if not todo or not todo.project_id:
                return
            project = await ProjectRepository(self.db).get_by_id(todo.project_id)
            if not project or project.project_type != ProjectType.BINARY_APP:
                return  # 仅 BINARY_APP 构建链路产出 BUILD

            content = prototype.content or {}
            build_status = content.get("build_status")
            if not build_status:
                return  # 无构建状态信息

            await ArtifactService(self.db).create_or_update_build(
                todo_id=todo_id,
                phase_id=prototype.phase_id,
                build_target=BuildTarget.TAURI_LINUX.value,
                artifact_path=content.get("artifact_path", "dist"),
                build_status=build_status,
            )
        except Exception as exc:
            logger.warning(
                "Produce BUILD artifact failed for todo %s: %s", todo_id, exc
            )

    async def _validate_extracted_artifact(
        self, artifact: Artifact, todo_id: uuid.UUID, *,
        constraint: "ProcessConstraint | None" = None,
        prior_artifacts: dict | None = None,
    ) -> "ConversationGateResult | None":
        """对话模式产出物门禁校验 (按 ProcessConstraint 分级)。

        先做依赖前置门 (dependency_graph)，再调 evaluate_conversation_gate。
        结果写入 artifact.content["_quality"]，返回 ConversationGateResult
        供调用方决定 tracker 状态: passed→PRODUCED，否则 IN_PROGRESS。

        这是对话/自驾模式的质量护栏——修复原先"产出即完成"的虚假状态。
        """
        from arc.application.execution.conversation_gate import (
            ConversationGateResult,
            evaluate_conversation_gate,
        )
        from arc.application.execution.gate_threshold import get_profile
        from arc.domain.planning.dependency_graph import missing_prerequisites
        from arc.domain.project.value_objects import ProcessConstraint

        constraint = constraint or ProcessConstraint.FREE
        profile = get_profile(constraint)

        try:
            qualified = prior_artifacts
            if qualified is None:
                qualified = await self._collect_qualified(todo_id)

            # 依赖前置门
            missing = missing_prerequisites(
                artifact.artifact_type.value, set(qualified.keys())
            )
            hard_block = (
                profile.dependency_block_mode == "hard"
                or artifact.artifact_type.value in profile.dependency_hard_block
            )

            if missing and hard_block:
                result = ConversationGateResult(
                    passed=False, score=0, threshold=profile.score_threshold,
                    gaps=[
                        f"前置交付物未达标: {', '.join(missing)}；"
                        f"请先完成并达标后再产出 {artifact.artifact_type.value}"
                    ],
                    suggestion="先产出并完善前置交付物。",
                    blocked_by_dependency=True,
                    checked_layers=["dependency"],
                )
                await self._write_quality(artifact, result)
                return result

            # 质量门禁 (按 GateProfile 分级的 4 层评估)
            # 接通 charter (系统治理底座) + conventions (用户规范) → LLM 评审遵守度 (波次3)
            charter_md, conventions = await self._get_project_governance(todo_id)
            capabilities = await self._get_phase_capabilities(
                todo_id, artifact.artifact_type
            )
            result = await evaluate_conversation_gate(
                artifact.artifact_type, artifact.content,
                constraint=constraint, prior_artifacts=qualified,
                conventions=conventions, charter=charter_md,
                capabilities=capabilities,
            )

            # 软模式前置警告 (不阻断，记录供 LLM 后续修正)
            if missing and not hard_block:
                result.dependency_warning = list(missing)

            await self._write_quality(artifact, result)
            logger.info(
                "Conversation artifact %s gate: passed=%s score=%s%s",
                artifact.artifact_type.value, result.passed, result.score,
                f" dep_warning={missing}" if missing else "",
            )
            return result
        except Exception as exc:
            logger.warning(
                "Artifact validation failed for %s: %s", artifact.id, exc,
                exc_info=True,
            )
            # 校验异常不阻断 (降级放行，避免门禁 bug 卡死整个对话)
            fallback = ConversationGateResult(
                passed=True, score=8, threshold=profile.score_threshold,
                suggestion="", checked_layers=["structural"],
            )
            await self._write_quality(artifact, fallback)
            return fallback

    async def _write_quality(self, artifact: Artifact, result) -> None:
        """把门禁结果写入 artifact.content["_quality"] 并持久化。"""
        if isinstance(artifact.content, dict):
            artifact.content["_quality"] = result.to_quality()
        else:
            artifact.content = {"_quality": result.to_quality()}
        await self.artifact_repo.update(artifact)

    async def _collect_qualified(self, todo_id: uuid.UUID) -> dict[str, dict]:
        """收集 todo 下已达标的 artifact (content._quality.passed=True)。"""
        arts = await self.artifact_repo.list_by_todo_id(todo_id)
        return {
            a.artifact_type.value: a.content
            for a in arts
            if isinstance(a.content, dict)
            and isinstance(a.content.get("_quality"), dict)
            and a.content["_quality"].get("passed") is True
        }

    async def _get_constraint(self, todo_id: uuid.UUID):
        """读取 todo 所属项目的 process_constraint，读不到降级 free。"""
        from arc.domain.project.value_objects import ProcessConstraint

        try:
            from arc.infrastructure.repositories.project import ProjectRepository
            from arc.infrastructure.repositories.todo import TodoRepository

            todo = await TodoRepository(self.db).get_by_id(todo_id)
            if not todo or not todo.project_id:
                return ProcessConstraint.FREE
            project = await ProjectRepository(self.db).get_by_id(todo.project_id)
            if not project:
                return ProcessConstraint.FREE
            return project.process_constraint
        except Exception:
            return ProcessConstraint.FREE

    async def _get_project_governance(self, todo_id: uuid.UUID) -> tuple[str, str]:
        """读取项目治理文本 (charter + conventions) 供门禁 LLM 评审。

        charter = 系统生成治理底座 (ProjectCharter.markdown),
        conventions = 用户手填增量。查不到降级 ("", "") 不阻断门禁。
        """
        try:
            from arc.infrastructure.repositories.project import ProjectRepository
            from arc.infrastructure.repositories.todo import TodoRepository

            todo = await TodoRepository(self.db).get_by_id(todo_id)
            if not todo or not todo.project_id:
                return "", ""
            project = await ProjectRepository(self.db).get_by_id(todo.project_id)
            if not project:
                return "", ""
            charter_md = project.charter.markdown if project.charter else ""
            return charter_md, project.conventions or ""
        except Exception:
            return "", ""

    async def _get_phase_capabilities(
        self, todo_id: uuid.UUID, artifact_type: ArtifactType
    ) -> str:
        """取该 artifact 所属环节启用能力的描述 (v6.8.0 W3.3)。

        供门禁 LLM 按环节能力规范生成检查项。查不到降级空串, 不阻断门禁
        (与 _get_project_governance 同模式)。
        """
        try:
            from arc.application.capability.service import CapabilityService
            from arc.application.execution.conversation_gate import _phase_for
            from arc.infrastructure.repositories.project import ProjectRepository
            from arc.infrastructure.repositories.todo import TodoRepository

            phase = _phase_for(artifact_type)
            if not phase:
                return ""
            todo = await TodoRepository(self.db).get_by_id(todo_id)
            if not todo or not todo.project_id:
                return ""
            project = await ProjectRepository(self.db).get_by_id(todo.project_id)
            if not project:
                return ""
            cap_ids = (
                (project.pipeline_config or {}).get("phase_capabilities") or {}
            ).get(phase.value)
            if not cap_ids:
                return ""
            uuids: list[uuid.UUID] = []
            for cid in cap_ids:
                try:
                    uuids.append(uuid.UUID(cid) if isinstance(cid, str) else cid)
                except (ValueError, AttributeError):
                    pass
            if not uuids:
                return ""
            caps = await CapabilityService(self.db).list_by_ids(uuids)
            active = [c for c in caps if c.is_active]
            if not active:
                return ""
            lines = []
            for cap in active:
                type_label = "技能" if cap.is_skill else "Agent"
                lines.append(f"- {cap.name} ({type_label})")
            return "\n".join(lines)
        except Exception:
            return ""

    async def get_or_create_tracker(
        self,
        todo_id: uuid.UUID,
        required_types: list[str],
    ) -> DeliverableTracker:
        """获取或创建DeliverableTracker。"""
        tracker = await self.tracker_repo.get_by_todo_id(todo_id)
        if tracker:
            return tracker

        tracker = DeliverableTracker(todo_id=todo_id)
        tracker.initialize(required_types)
        return await self.tracker_repo.create(tracker)
