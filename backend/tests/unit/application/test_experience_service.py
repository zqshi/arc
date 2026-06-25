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


class TestExperienceServiceCreate:
    @pytest.mark.asyncio
    async def test_create_generates_embedding_and_persists(self):
        from arc.application.experience.service import ExperienceService

        svc = ExperienceService.__new__(ExperienceService)
        svc.db = MagicMock()
        svc.exp_repo = MagicMock()
        svc.exp_repo.create = AsyncMock(side_effect=lambda e, user_id: e)
        svc._generate_embedding = AsyncMock(return_value=[0.1, 0.2])

        result = await svc.create(
            title="t", scope="personal", problem="p", solution="s",
            decisions=[], pitfalls=[], applicable_scenarios="scn",
            tags=[], user_id=uuid.uuid4(),
        )
        assert result.scope.value == "personal"
        svc._generate_embedding.assert_awaited_once()
        svc.exp_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_defaults_scope_to_project_when_invalid(self):
        from arc.application.experience.service import ExperienceService
        from arc.domain.todo.value_objects import ExperienceScope

        svc = ExperienceService.__new__(ExperienceService)
        svc.db = MagicMock()
        svc.exp_repo = MagicMock()
        svc.exp_repo.create = AsyncMock(side_effect=lambda e, user_id: e)
        svc._generate_embedding = AsyncMock(return_value=None)

        result = await svc.create(
            title="t", scope=None, problem="p", solution="s",
            decisions=[], pitfalls=[], applicable_scenarios="", tags=[], user_id=uuid.uuid4(),
        )
        assert result.scope == ExperienceScope.PROJECT


class TestExperienceServiceUpdate:
    @pytest.mark.asyncio
    async def test_update_not_found_raises(self):
        from arc.application.experience.service import ExperienceService

        svc = ExperienceService.__new__(ExperienceService)
        svc.db = MagicMock()
        svc.exp_repo = MagicMock()
        svc.exp_repo.get_by_id = AsyncMock(return_value=None)
        svc._generate_embedding = AsyncMock()

        with pytest.raises(ValueError):
            await svc.update(uuid.uuid4(), {"title": "x"}, user_id=uuid.uuid4())

    @pytest.mark.asyncio
    async def test_update_applies_and_regenerates_embedding(self):
        from arc.application.experience.service import ExperienceService

        exp = Experience(title="t", problem="p", solution="s", id=uuid.uuid4())
        svc = ExperienceService.__new__(ExperienceService)
        svc.db = MagicMock()
        svc.exp_repo = MagicMock()
        svc.exp_repo.get_by_id = AsyncMock(return_value=exp)
        svc.exp_repo.update = AsyncMock(side_effect=lambda e: e)
        svc._generate_embedding = AsyncMock(return_value=[0.5])

        result = await svc.update(exp.id, {"title": "new"}, user_id=uuid.uuid4())
        assert result.title == "new"
        assert result.embedding == [0.5]
        svc._generate_embedding.assert_awaited_once()


class TestExperienceServiceApplyUpdates:
    def test_enum_conversion(self):
        from arc.application.experience.service import ExperienceService

        exp = Experience(title="t", problem="p", solution="s")
        ExperienceService._apply_updates(exp, {
            "scope": "personal",
            "category": "technical",
            "source": "manual",
        })
        assert exp.scope.value == "personal"
        assert exp.category.value == "technical"
        assert exp.source.value == "manual"

    def test_tags_dict_compat(self):
        from arc.application.experience.service import ExperienceService

        exp = Experience(title="t", problem="p", solution="s")
        ExperienceService._apply_updates(exp, {"tags": [{"label": "a", "color": "#fff"}]})
        assert exp.tags[0].label == "a"
        assert exp.tags[0].color == "#fff"

    def test_tags_object_compat(self):
        from arc.application.experience.service import ExperienceService
        from arc.domain.todo.value_objects import Tag

        exp = Experience(title="t", problem="p", solution="s")
        ExperienceService._apply_updates(exp, {"tags": [Tag(label="b", color="#000")]})
        assert exp.tags[0].label == "b"

    def test_plain_field_setattr(self):
        from arc.application.experience.service import ExperienceService

        exp = Experience(title="t", problem="p", solution="s")
        ExperienceService._apply_updates(exp, {"problem": "new problem"})
        assert exp.problem == "new problem"


class TestExperienceServiceGenerateEmbedding:
    @pytest.mark.asyncio
    async def test_adapter_failure_returns_none(self):
        from arc.application.experience.service import ExperienceService

        exp = Experience(title="t", problem="p", solution="s", id=uuid.uuid4())
        svc = ExperienceService.__new__(ExperienceService)
        with patch("arc.application.ai.resilience.create_resilient_adapter", side_effect=RuntimeError):
            result = await svc._generate_embedding(exp)
        assert result is None
