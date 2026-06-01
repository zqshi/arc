"""ModelUpgradeOrchestrator — 领域模型升级全流程编排。

按策略执行升级:
- BLOCK: 暂停高风险需求 → 应用变更 → 自动恢复低风险需求
- DEFER: 标记反馈为 deferred，不执行变更
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.application.review.impact_analyzer import ImpactAnalyzer, assess_risk
from arc.domain.artifact.repository import ArtifactRepository
from arc.domain.project.entity import Project
from arc.domain.project.repository import AbstractProjectRepository
from arc.domain.project.value_objects import ModelChangeTrigger
from arc.domain.review.entity import ReviewFeedback
from arc.domain.review.repository import IReviewFeedbackRepository
from arc.domain.review.value_objects import (
    ImpactReport,
    ModelChangeScope,
    RiskLevel,
    UpgradeStrategy,
)
from arc.domain.todo.repository import ITodoRepository
from arc.domain.todo.value_objects import TodoStatus

logger = logging.getLogger(__name__)


@dataclass
class UpgradeResult:
    """升级执行结果。"""

    success: bool
    strategy: UpgradeStrategy
    new_model_version: int | None = None
    suspended_todo_ids: list[uuid.UUID] = field(default_factory=list)
    auto_resumed_todo_ids: list[uuid.UUID] = field(default_factory=list)
    deferred_feedback_ids: list[uuid.UUID] = field(default_factory=list)
    error: str = ""


class ModelUpgradeOrchestrator:
    """领域模型升级全流程编排器。"""

    def __init__(
        self,
        project_repo: AbstractProjectRepository,
        todo_repo: ITodoRepository,
        artifact_repo: ArtifactRepository,
        feedback_repo: IReviewFeedbackRepository,
    ):
        self._project_repo = project_repo
        self._todo_repo = todo_repo
        self._artifact_repo = artifact_repo
        self._feedback_repo = feedback_repo

    async def execute(
        self,
        project_id: uuid.UUID,
        feedback_ids: list[uuid.UUID],
        new_model: dict,
        strategy: UpgradeStrategy,
    ) -> UpgradeResult:
        """执行模型升级。

        Args:
            project_id: 项目 ID
            feedback_ids: 要处理的反馈 IDs
            new_model: 升级后的新模型内容
            strategy: 升级策略

        Returns:
            UpgradeResult
        """
        if strategy == UpgradeStrategy.DEFER:
            return await self._execute_defer(feedback_ids)

        return await self._execute_block(project_id, feedback_ids, new_model)

    async def _execute_defer(
        self, feedback_ids: list[uuid.UUID]
    ) -> UpgradeResult:
        """延迟策略：标记反馈为 deferred。"""
        deferred: list[uuid.UUID] = []
        for fid in feedback_ids:
            fb = await self._feedback_repo.get_by_id(fid)
            if fb and not fb.is_resolved:
                fb.defer("延迟到下一版本处理")
                await self._feedback_repo.update(fb)
                deferred.append(fid)

        return UpgradeResult(
            success=True,
            strategy=UpgradeStrategy.DEFER,
            deferred_feedback_ids=deferred,
        )

    async def _execute_block(
        self,
        project_id: uuid.UUID,
        feedback_ids: list[uuid.UUID],
        new_model: dict,
    ) -> UpgradeResult:
        """阻断策略：暂停高风险需求 → 应用变更 → 恢复低风险需求。"""
        # 1. 获取项目
        project = await self._project_repo.get_by_id(project_id)
        if not project:
            return UpgradeResult(success=False, strategy=UpgradeStrategy.BLOCK, error="项目不存在")

        old_version = project.domain_model_version

        # 2. 确定受影响的聚合
        affected_aggs = self._extract_affected_aggregates(new_model, project.domain_model)

        # 3. 影响分析
        analyzer = ImpactAnalyzer(self._todo_repo, self._artifact_repo)
        # 使用最严格的 scope 来做影响判断
        scope = self._determine_scope(feedback_ids)
        report = await analyzer.analyze(project_id, list(affected_aggs), scope)

        # 4. 暂停高风险 todos
        suspended: list[uuid.UUID] = []
        auto_resumed: list[uuid.UUID] = []

        for item in report.items:
            if item.risk >= RiskLevel.HIGH:
                todo = await self._todo_repo.get_by_id(item.todo_id)
                if todo and todo.status == TodoStatus.ACTIVE:
                    todo.suspend_for_upgrade(
                        f"等待领域模型升级: {', '.join(item.affected_aggregates)}",
                        old_version,
                    )
                    await self._todo_repo.update(todo)
                    suspended.append(item.todo_id)

        # 5. 应用模型变更
        new_version = project.upgrade_domain_model(
            new_model,
            trigger=ModelChangeTrigger.UPGRADE,
            trigger_todo_id="",
        )
        await self._project_repo.update(project)

        # 6. 标记反馈为 accepted
        for fid in feedback_ids:
            fb = await self._feedback_repo.get_by_id(fid)
            if fb and not fb.is_resolved:
                fb.accept(f"已升级到 v{new_version}")
                await self._feedback_repo.update(fb)

        # 7. 自动恢复低风险 todos
        for item in report.items:
            if item.risk < RiskLevel.HIGH:
                todo = await self._todo_repo.get_by_id(item.todo_id)
                if todo and todo.is_suspended:
                    todo.resume_after_upgrade()
                    await self._todo_repo.update(todo)
                    auto_resumed.append(item.todo_id)

        logger.info(
            "Model upgrade complete: project=%s v%d→v%d, suspended=%d, auto_resumed=%d",
            project_id, old_version, new_version, len(suspended), len(auto_resumed),
        )

        return UpgradeResult(
            success=True,
            strategy=UpgradeStrategy.BLOCK,
            new_model_version=new_version,
            suspended_todo_ids=suspended,
            auto_resumed_todo_ids=auto_resumed,
        )

    def _determine_scope(self, feedback_ids: list[uuid.UUID]) -> ModelChangeScope:
        """从反馈 IDs 确定最严格的变更范围（用于影响分析）。

        由于此处无法异步查询，使用最严格的默认值。
        实际调用方应在调用前确定 scope。
        """
        # 默认使用 STRUCTURAL — 足够谨慎但不过度
        return ModelChangeScope.STRUCTURAL

    @staticmethod
    def _extract_affected_aggregates(new_model: dict, old_model: dict) -> set[str]:
        """比较新旧模型，提取变化的聚合名称。"""
        new_aggs = {a.get("name", "") for a in new_model.get("aggregates", []) if isinstance(a, dict)}
        old_aggs = {a.get("name", "") for a in old_model.get("aggregates", []) if isinstance(a, dict)}

        # 新增的 + 删除的 + 内容变化的
        added = new_aggs - old_aggs
        removed = old_aggs - new_aggs

        # 检查同名聚合内容变化
        changed: set[str] = set()
        old_by_name = {a.get("name"): a for a in old_model.get("aggregates", []) if isinstance(a, dict)}
        new_by_name = {a.get("name"): a for a in new_model.get("aggregates", []) if isinstance(a, dict)}
        for name in new_aggs & old_aggs:
            if old_by_name.get(name) != new_by_name.get(name):
                changed.add(name)

        return (added | removed | changed) - {""}
