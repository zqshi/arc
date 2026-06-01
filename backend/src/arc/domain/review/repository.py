"""ReviewFeedback 仓储接口。"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from arc.domain.review.entity import ReviewFeedback
from arc.domain.review.value_objects import ReviewFeedbackStatus


class IReviewFeedbackRepository(ABC):
    @abstractmethod
    async def create(self, feedback: ReviewFeedback) -> ReviewFeedback: ...

    @abstractmethod
    async def get_by_id(self, feedback_id: uuid.UUID) -> ReviewFeedback | None: ...

    @abstractmethod
    async def list_by_project(
        self,
        project_id: uuid.UUID,
        *,
        status: ReviewFeedbackStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[ReviewFeedback]: ...

    @abstractmethod
    async def update(self, feedback: ReviewFeedback) -> None: ...

    @abstractmethod
    async def count_by_project(
        self,
        project_id: uuid.UUID,
        *,
        status: ReviewFeedbackStatus | None = None,
    ) -> int: ...
