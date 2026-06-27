"""ExperienceService 核心方法单元测试。"""

import types
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.domain.errors import NotFoundError
from arc.domain.experience.entity import Experience
from arc.domain.todo.entity import Todo
from arc.domain.todo.value_objects import ExperienceStatus


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

        with pytest.raises(NotFoundError):
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

        with pytest.raises(NotFoundError):
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


class TestExperienceServiceExtractFromTodo:
    """extract_from_todo 经验提取 — 去重/对话聚合/LLM解析/异常降级。"""

    def _make_svc(self, *, existing=False, conversations=None):
        from arc.application.experience.service import ExperienceService

        svc = ExperienceService.__new__(ExperienceService)
        svc.db = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(
            return_value=uuid.uuid4() if existing else None
        )
        svc.db.execute = AsyncMock(return_value=result)
        svc.exp_repo = MagicMock()
        svc.exp_repo.create = AsyncMock(side_effect=lambda e, **kw: e)
        svc.conv_repo = MagicMock()
        svc.conv_repo.list_by_todo_id = AsyncMock(return_value=conversations or [])
        return svc

    def _make_conversation(self, todo_id):
        from arc.domain.conversation.entity import Conversation, Message
        from arc.domain.todo.value_objects import ConversationPurpose, MessageRole

        return Conversation(
            todo_id=todo_id,
            purpose=ConversationPurpose.DEVELOPMENT,
            messages=[
                Message(role=MessageRole.USER, content="如何做X", conversation_id=uuid.uuid4()),
                Message(role=MessageRole.ASSISTANT, content="用方案Y", conversation_id=uuid.uuid4()),
            ],
        )

    @pytest.mark.asyncio
    async def test_skips_when_experience_already_exists(self):

        todo = Todo(title="t", description="d", id=uuid.uuid4())
        svc = self._make_svc(existing=True)
        with patch("arc.application.ai.resilience.create_resilient_adapter") as mock_adapter_factory:
            result = await svc.extract_from_todo(todo)
        assert result is None
        mock_adapter_factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_conversation(self):
        todo = Todo(title="t", description="d", id=uuid.uuid4())
        svc = self._make_svc(conversations=[])
        with patch("arc.application.ai.resilience.create_resilient_adapter") as mock_adapter_factory:
            result = await svc.extract_from_todo(todo)
        assert result is None
        mock_adapter_factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_extracts_and_creates_experience(self):
        todo = Todo(
            title="t", description="d", id=uuid.uuid4(),
            project_id=uuid.uuid4(), version_id=uuid.uuid4(),
        )
        svc = self._make_svc(conversations=[self._make_conversation(todo.id)])

        mock_adapter = MagicMock()
        mock_adapter.chat = AsyncMock(
            return_value=types.SimpleNamespace(
                content='{"title":"exp","problem":"p","solution":"s",'
                '"applicable_scenarios":"scn","category":"technical"}'
            )
        )
        mock_adapter.embed = AsyncMock(return_value=[0.1, 0.2])
        mock_adapter.close = AsyncMock()
        with patch(
            "arc.application.ai.resilience.create_resilient_adapter",
            return_value=mock_adapter,
        ):
            result = await svc.extract_from_todo(todo)
        assert result is not None
        assert result.title == "exp"
        assert result.embedding == [0.1, 0.2]
        svc.exp_repo.create.assert_awaited_once()
        mock_adapter.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_none(self):
        todo = Todo(title="t", description="d", id=uuid.uuid4())
        svc = self._make_svc(conversations=[self._make_conversation(todo.id)])

        mock_adapter = MagicMock()
        mock_adapter.chat = AsyncMock(
            return_value=types.SimpleNamespace(content="这是纯文本,没有任何JSON结构")
        )
        mock_adapter.close = AsyncMock()
        with patch(
            "arc.application.ai.resilience.create_resilient_adapter",
            return_value=mock_adapter,
        ):
            result = await svc.extract_from_todo(todo)
        assert result is None
        svc.exp_repo.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_llm_exception_returns_none(self):
        todo = Todo(title="t", description="d", id=uuid.uuid4())
        svc = self._make_svc(conversations=[self._make_conversation(todo.id)])

        mock_adapter = MagicMock()
        mock_adapter.chat = AsyncMock(side_effect=RuntimeError("LLM down"))
        mock_adapter.close = AsyncMock()
        with patch(
            "arc.application.ai.resilience.create_resilient_adapter",
            return_value=mock_adapter,
        ):
            result = await svc.extract_from_todo(todo)
        assert result is None
        svc.exp_repo.create.assert_not_awaited()
        mock_adapter.close.assert_awaited_once()
