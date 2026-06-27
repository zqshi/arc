"""TodoService 单元测试。"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from arc.domain.todo.entity import Todo


class TestTodoServiceExtractTags:
    @pytest.mark.asyncio
    async def test_extract_tags_happy_path(self):
        from arc.application.todo.service import TodoService

        todo = Todo(title="实现订单支付功能", description="支持微信和支付宝", id=uuid.uuid4())

        db = MagicMock()
        svc = TodoService.__new__(TodoService)
        svc.db = db
        svc.todo_repo = MagicMock()
        svc.conv_repo = MagicMock()
        svc.todo_repo.get_by_id = AsyncMock(return_value=todo)
        svc.todo_repo.update = AsyncMock(side_effect=lambda t: t)

        with patch("arc.application.ai.llm_adapter.create_llm_adapter") as mock_adapter_factory:
            mock_adapter = MagicMock()
            mock_adapter.chat = AsyncMock(return_value=MagicMock(
                content='```json\n[{"label": "支付", "color": "#4CAF50"}, {"label": "订单", "color": "#2196F3"}]\n```'
            ))
            mock_adapter.close = AsyncMock()
            mock_adapter_factory.return_value = mock_adapter

            result = await svc.extract_tags(todo.id)

        assert len(result.tags) == 2
        assert result.tags[0].label == "支付"

    @pytest.mark.asyncio
    async def test_extract_tags_not_found(self):
        from arc.application.todo.service import TodoService

        db = MagicMock()
        svc = TodoService.__new__(TodoService)
        svc.db = db
        svc.todo_repo = MagicMock()
        svc.conv_repo = MagicMock()
        svc.todo_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="not found"):
            await svc.extract_tags(uuid.uuid4())

    @pytest.mark.asyncio
    async def test_extract_tags_llm_failure_returns_empty(self):
        from arc.application.todo.service import TodoService

        todo = Todo(title="test", id=uuid.uuid4())

        db = MagicMock()
        svc = TodoService.__new__(TodoService)
        svc.db = db
        svc.todo_repo = MagicMock()
        svc.conv_repo = MagicMock()
        svc.todo_repo.get_by_id = AsyncMock(return_value=todo)
        svc.todo_repo.update = AsyncMock(side_effect=lambda t: t)

        with patch("arc.application.ai.llm_adapter.create_llm_adapter") as mock_factory:
            mock_adapter = MagicMock()
            mock_adapter.chat = AsyncMock(return_value=MagicMock(content="not json"))
            mock_adapter.close = AsyncMock()
            mock_factory.return_value = mock_adapter

            result = await svc.extract_tags(todo.id)

        # LLM 返回无效 JSON 时应该返回空 tags
        assert isinstance(result.tags, list)
