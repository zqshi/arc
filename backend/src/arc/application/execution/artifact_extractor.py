"""从AI对话输出中提取结构化产出物并自动归档。"""

from __future__ import annotations

import json
import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from arc.application.ai.json_extract import extract_json
from arc.domain.artifact.entity import Artifact
from arc.domain.artifact.value_objects import ArtifactType
from arc.domain.planning.entity import DeliverableTracker
from arc.infrastructure.repositories.artifact import ArtifactRepository
from arc.infrastructure.repositories.planning import DeliverableTrackerRepository

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

        for artifact_type_str, json_str in matches:
            try:
                artifact_type = ArtifactType(artifact_type_str)
            except ValueError:
                logger.warning("Unknown artifact type in DELIVERABLE marker: %s", artifact_type_str)
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

            if tracker:
                tracker.mark_produced(artifact_type_str)

        if tracker and extracted:
            await self.tracker_repo.update(tracker)

        # 对话模式产出物也执行 gate 校验 — 不阻断但记录质量信号
        for art in extracted:
            await self._validate_extracted_artifact(art, todo_id)

        for art in extracted:
            if art.artifact_type == ArtifactType.TECH_ARCHITECTURE:
                await self._try_extract_domain_model(todo_id, art.content)

        # requirement_spec 产出后，智能推断适用的交付物范围
        for art in extracted:
            if art.artifact_type == ArtifactType.REQUIREMENT_SPEC and tracker:
                await self._infer_deliverable_scope(tracker, art.content)

        return extracted

    async def _infer_deliverable_scope(
        self, tracker: DeliverableTracker, req_spec: dict,
    ) -> None:
        """根据 requirement_spec 内容推断适用的交付物范围，裁剪 tracker.required。

        规则基于需求类型特征词匹配，不调用 LLM（零延迟）：
        - 无 UI 相关描述 → 跳过 interaction_design, ui_spec, prototype
        - 纯 bug 修复 → 只保留核心四项
        - 其他保留全量
        """
        from arc.domain.planning.value_objects import DeliverableStatus
        from arc.domain.project.value_objects import REQUIRED_DELIVERABLES

        # 提取信号
        stories = req_spec.get("user_stories", [])
        boundaries = req_spec.get("boundaries", {})
        in_scope = boundaries.get("in_scope", []) if isinstance(boundaries, dict) else []
        background = req_spec.get("background", "")
        all_text = (
            background + " "
            + " ".join(str(s) for s in stories)
            + " ".join(str(s) for s in in_scope)
        ).lower()

        # 判断需求类型
        has_ui_signal = any(kw in all_text for kw in [
            "ui", "界面", "页面", "交互", "前端", "组件", "按钮", "表单",
            "弹窗", "列表", "视觉", "样式", "布局", "响应式", "移动端",
        ])
        is_bug_fix = any(kw in all_text for kw in [
            "bug", "修复", "fix", "回归", "崩溃", "报错", "异常",
        ]) and not any(kw in all_text for kw in ["新增", "新功能", "feature"])

        has_deploy_signal = any(kw in all_text for kw in [
            "部署", "上线", "deploy", "ci", "cd", "docker", "k8s",
        ])

        # 计算适用范围
        skip_types: set[str] = set()

        if not has_ui_signal:
            skip_types.update(["interaction_design", "ui_spec", "prototype"])

        if is_bug_fix:
            skip_types.update([
                "interaction_design", "ui_spec", "prototype",
                "tech_architecture", "deploy_report",
            ])

        if not has_deploy_signal and not is_bug_fix:
            # 默认保留 deploy_report，但纯前端任务可跳过
            has_backend_signal = any(kw in all_text for kw in [
                "api", "后端", "数据库", "服务", "接口", "backend",
            ])
            if not has_backend_signal and has_ui_signal:
                skip_types.add("deploy_report")

        # 应用裁剪
        if not skip_types:
            return  # 全量保留，不修改

        new_required = [d for d in REQUIRED_DELIVERABLES if d not in skip_types]

        # 不能裁剪到少于 4 项（最低保障）
        if len(new_required) < 4:
            return

        # 更新 tracker
        tracker.required = new_required
        # 移除被跳过项的 pending 状态（已产出的保留）
        for skip_type in skip_types:
            if tracker.deliverables.get(skip_type) == DeliverableStatus.PENDING:
                del tracker.deliverables[skip_type]

        await self.tracker_repo.update(tracker)
        logger.info(
            "Inferred deliverable scope: skipped %s, remaining %d items",
            skip_types, len(new_required),
        )

    async def _try_extract_domain_model(
        self, todo_id: uuid.UUID, content: dict
    ) -> None:
        from arc.application.execution.domain_model_extractor import (
            DomainModelExtractor,
        )

        try:
            extractor = DomainModelExtractor(self.db)
            updated = await extractor.extract_and_merge(todo_id, content)

            # 提取成功后自动触发评审闭环
            if updated:
                await self._try_review_after_extract(todo_id)
        except Exception:
            logger.warning(
                "Domain model extraction failed for todo %s", todo_id, exc_info=True
            )

    async def _validate_extracted_artifact(
        self, artifact: Artifact, todo_id: uuid.UUID
    ) -> None:
        """对话模式产出物 gate 校验 — 不阻断，记录质量信号到 artifact metadata。

        质量信号用途:
        - 前端侧边栏展示产出物质量状态（绿/黄/红）
        - tracker 中标记需要修正的产出物
        - 为后续"建议用户确认"提供依据
        """
        from arc.application.pipeline.gate import check_required_fields
        from arc.domain.artifact.value_objects import PHASE_ARTIFACT_MAP
        from arc.domain.pipeline.value_objects import PhaseType

        # 映射 artifact_type → phase_type
        phase_type = None
        for pt, atypes in PHASE_ARTIFACT_MAP.items():
            if artifact.artifact_type in atypes:
                phase_type = pt
                break

        if not phase_type:
            return

        try:
            # 快速结构检查（不调 LLM，控制成本）
            gaps = check_required_fields(phase_type, artifact.content)

            # 方法论校验（架构阶段）
            from arc.application.pipeline.gate import _check_methodology
            methodology_gaps = _check_methodology(phase_type, artifact.content)
            gaps.extend(methodology_gaps)

            quality_signal = {
                "gate_passed": len(gaps) == 0,
                "structural_gaps": gaps[:5],  # 最多记录5条
                "checked_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            }

            # 更新 artifact content 的 _quality 元数据
            if isinstance(artifact.content, dict):
                artifact.content["_quality"] = quality_signal
                await self.artifact_repo.update(artifact)

            if gaps:
                logger.info(
                    "Conversation artifact %s has %d quality gaps: %s",
                    artifact.artifact_type.value, len(gaps), gaps[:3],
                )
        except Exception as exc:
            logger.debug("Artifact validation skipped for %s: %s", artifact.id, exc)

    async def _try_review_after_extract(self, todo_id: uuid.UUID) -> None:
        """领域模型提取后自动触发评审，产出 ReviewFeedback。"""
        from arc.application.review.service import ReviewService
        from arc.infrastructure.repositories.review import ReviewFeedbackRepository
        from arc.infrastructure.repositories.todo import TodoRepository

        try:
            todo_repo = TodoRepository(self.db)
            todo = await todo_repo.get_by_id(todo_id)
            if not todo or not todo.project_id:
                return

            from arc.infrastructure.repositories.project import ProjectRepository

            project_repo = ProjectRepository(self.db)
            project = await project_repo.get_by_id(todo.project_id)
            if not project or not project.domain_model:
                return

            feedback_repo = ReviewFeedbackRepository(self.db)
            svc = ReviewService(feedback_repo)
            await svc.validate_and_persist(
                project.id, project.domain_model, source_todo_id=todo_id,
            )
        except Exception:
            logger.debug("Auto-review after extract skipped for todo %s", todo_id, exc_info=True)

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
