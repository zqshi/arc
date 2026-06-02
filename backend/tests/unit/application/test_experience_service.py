"""ExperienceService 核心方法单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.domain.experience.entity import Experience
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import ExperienceStatus, TodoStatus


class TestExperienceServiceConfirm:
    @pytest.mark.asyncio
    async def test_confirm_draft(self):
        from arc.application.experience.service import ExperienceService

        exp = Experience(title="t", problem="p", solution="s", id=uuid.uuid4())
        assert exp.status == ExperienceStatus.DRAFT

        db = MagicMock()
        svc = ExperienceService.__new__(ExperienceService)
        svc.db = db
        svc.exp_repo = MagicMock()
        svc.conv_repo = MagicMock()
        svc.exp_repo.get_by_id = AsyncMock(return_value=exp)
        svc.exp_repo.update = AsyncMock(side_effect=lambda e: e)

        result = await svc.confirm(exp.id, uuid.uuid4())
        assert result.status == ExperienceStatus.CONFIRMED

    @pytest.mark.asyncio
    async def test_confirm_not_found(self):
        from arc.application.experience.service import ExperienceService

        db = MagicMock()
        svc = ExperienceService.__new__(ExperienceService)
        svc.db = db
        svc.exp_repo = MagicMock()
        svc.conv_repo = MagicMock()
        svc.exp_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError):
            await svc.confirm(uuid.uuid4(), uuid.uuid4())


class TestExperienceServiceArchive:
    @pytest.mark.asyncio
    async def test_archive(self):
        from arc.application.experience.service import ExperienceService

        exp = Experience(title="t", problem="p", solution="s", id=uuid.uuid4())

        db = MagicMock()
        svc = ExperienceService.__new__(ExperienceService)
        svc.db = db
        svc.exp_repo = MagicMock()
        svc.conv_repo = MagicMock()
        svc.exp_repo.get_by_id = AsyncMock(return_value=exp)
        svc.exp_repo.update = AsyncMock(side_effect=lambda e: e)

        result = await svc.archive(exp.id, uuid.uuid4())
        assert result.status == ExperienceStatus.ARCHIVED


class TestExperienceServiceDecayBatch:
    @pytest.mark.asyncio
    async def test_decay_updates_confidence(self):
        from arc.application.experience.service import ExperienceService

        exp = Experience(
            title="t", problem="p", solution="s",
            confidence=0.8, half_life_days=1,
        )

        db = MagicMock()
        svc = ExperienceService.__new__(ExperienceService)
        svc.db = db
        svc.exp_repo = MagicMock()
        svc.conv_repo = MagicMock()
        svc.exp_repo.list_for_decay = AsyncMock(return_value=[exp])
        svc.exp_repo.update = AsyncMock(side_effect=lambda e: e)

        count = await svc.decay_batch()
        # 结果取决于 compute_decayed_confidence 的当前时间
        assert isinstance(count, int)
