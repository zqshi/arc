"""ReviewService — Validator 评审闭环服务。

将 validate_domain_model() 的输出自动转化为持久化的 ReviewFeedback，
完成"评审 → 反馈 → 行动"闭环。
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from arc.application.review.classifier import classify_change_scope
from arc.domain.errors import AppError, NotFoundError
from arc.domain.review.entity import ReviewFeedback
from arc.domain.review.repository import IReviewFeedbackRepository
from arc.domain.review.value_objects import (
    ReviewIssue,
    ReviewIssueCategory,
    ReviewIssueSeverity,
)

if TYPE_CHECKING:
    pass  # 保留 TYPE_CHECKING block 以备后续类型标注使用

logger = logging.getLogger(__name__)


class ReviewService:
    """评审反馈管理服务。"""

    def __init__(self, feedback_repo: IReviewFeedbackRepository):
        self._feedback_repo = feedback_repo

    async def validate_and_persist(
        self,
        project_id: uuid.UUID,
        domain_model: dict,
        *,
        source_todo_id: uuid.UUID | None = None,
    ) -> tuple[list[ReviewFeedback], dict]:
        """执行领域模型评审并将 issues 持久化为 ReviewFeedback。

        Returns:
            (新创建的 ReviewFeedback 列表, 原始评审结果 dict)
        """
        from arc.application.execution.domain_model_validator import validate_domain_model

        raw_result = await validate_domain_model(domain_model)
        issues = raw_result.get("issues", [])

        if not issues:
            logger.info("Domain model review: no issues found for project %s", project_id)
            return [], raw_result

        model_version = domain_model.get("version", 0)
        feedbacks: list[ReviewFeedback] = []

        for issue_data in issues:
            issue = _parse_issue(issue_data)
            scope = classify_change_scope(issue.category, issue.severity)

            feedback = ReviewFeedback(
                project_id=project_id,
                issue=issue,
                scope=scope,
                source_todo_id=source_todo_id,
                model_version=model_version,
            )
            created = await self._feedback_repo.create(feedback)
            feedbacks.append(created)

        logger.info(
            "Review: %d feedbacks created for project %s (model v%d)",
            len(feedbacks), project_id, model_version,
        )
        return feedbacks, raw_result

    async def resolve_feedback(
        self,
        feedback_id: uuid.UUID,
        action: str,
        note: str = "",
    ) -> ReviewFeedback:
        """处理一条反馈: accept / defer / reject。

        Raises:
            ValueError: 反馈不存在或 action 无效。
        """
        feedback = await self._feedback_repo.get_by_id(feedback_id)
        if feedback is None:
            raise NotFoundError(f"Feedback {feedback_id} not found")

        if action == "accept":
            feedback.accept(note)
        elif action == "defer":
            feedback.defer(note)
        elif action == "reject":
            feedback.reject(note)
        else:
            raise AppError(f"Invalid action: {action!r}, expected accept/defer/reject")

        await self._feedback_repo.update(feedback)
        return feedback


def _parse_issue(data: dict) -> ReviewIssue:
    """将 Validator 返回的 issue dict 解析为 ReviewIssue 值对象。"""
    try:
        severity = ReviewIssueSeverity(data.get("severity", "info"))
    except ValueError:
        severity = ReviewIssueSeverity.INFO

    try:
        category = ReviewIssueCategory(data.get("category", "completeness"))
    except ValueError:
        category = ReviewIssueCategory.COMPLETENESS

    return ReviewIssue(
        severity=severity,
        category=category,
        title=data.get("title", ""),
        detail=data.get("detail", ""),
        suggestion=data.get("suggestion", ""),
    )
