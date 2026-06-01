from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from arc.domain.review.entity import ReviewFeedback
from arc.domain.review.repository import IReviewFeedbackRepository
from arc.domain.review.value_objects import (
    ModelChangeScope,
    ReviewFeedbackStatus,
    ReviewIssue,
    ReviewIssueCategory,
    ReviewIssueSeverity,
)
from arc.infrastructure.models.review import ReviewFeedbackModel


class ReviewFeedbackRepository(IReviewFeedbackRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, feedback: ReviewFeedback) -> ReviewFeedback:
        model = ReviewFeedbackModel(
            id=feedback.id,
            project_id=feedback.project_id,
            source_todo_id=feedback.source_todo_id,
            model_version=feedback.model_version,
            scope=feedback.scope.value,
            status=feedback.status.value,
            issue=_issue_to_dict(feedback.issue),
            resolution_note=feedback.resolution_note or None,
            resolved_at=feedback.resolved_at,
        )
        self.db.add(model)
        await self.db.flush()
        return feedback

    async def get_by_id(self, feedback_id: uuid.UUID) -> ReviewFeedback | None:
        result = await self.db.execute(
            select(ReviewFeedbackModel).where(ReviewFeedbackModel.id == feedback_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return _to_entity(model)

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        *,
        status: ReviewFeedbackStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ReviewFeedback]:
        stmt = (
            select(ReviewFeedbackModel)
            .where(ReviewFeedbackModel.project_id == project_id)
            .order_by(ReviewFeedbackModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(ReviewFeedbackModel.status == status.value)
        result = await self.db.execute(stmt)
        return [_to_entity(m) for m in result.scalars().all()]

    async def update(self, feedback: ReviewFeedback) -> None:
        result = await self.db.execute(
            select(ReviewFeedbackModel).where(ReviewFeedbackModel.id == feedback.id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return
        model.status = feedback.status.value
        model.resolution_note = feedback.resolution_note or None
        model.resolved_at = feedback.resolved_at
        await self.db.flush()

    async def count_by_project(
        self,
        project_id: uuid.UUID,
        *,
        status: ReviewFeedbackStatus | None = None,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(ReviewFeedbackModel)
            .where(ReviewFeedbackModel.project_id == project_id)
        )
        if status is not None:
            stmt = stmt.where(ReviewFeedbackModel.status == status.value)
        result = await self.db.execute(stmt)
        return result.scalar_one()


def _issue_to_dict(issue: ReviewIssue) -> dict:
    return {
        "severity": issue.severity.value,
        "category": issue.category.value,
        "title": issue.title,
        "detail": issue.detail,
        "suggestion": issue.suggestion,
    }


def _to_entity(model: ReviewFeedbackModel) -> ReviewFeedback:
    issue_data = model.issue or {}
    try:
        severity = ReviewIssueSeverity(issue_data.get("severity", "info"))
    except ValueError:
        severity = ReviewIssueSeverity.INFO
    try:
        category = ReviewIssueCategory(issue_data.get("category", "completeness"))
    except ValueError:
        category = ReviewIssueCategory.COMPLETENESS

    return ReviewFeedback(
        id=model.id,
        project_id=model.project_id,
        issue=ReviewIssue(
            severity=severity,
            category=category,
            title=issue_data.get("title", ""),
            detail=issue_data.get("detail", ""),
            suggestion=issue_data.get("suggestion", ""),
        ),
        scope=ModelChangeScope(model.scope),
        source_todo_id=model.source_todo_id,
        model_version=model.model_version or 0,
        status=ReviewFeedbackStatus(model.status),
        resolution_note=model.resolution_note or "",
        created_at=model.created_at,
        resolved_at=model.resolved_at,
    )
