"""ConversationService 委托行为单元测试。

重构后 ConversationService 委托 ExecutionEngine(与 ConversationExecutionService 同款),
本测试验证委托参数与事件透传,不再测试已删除的 prompt 构建死代码。
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.conversation.service import ConversationService
from arc.domain.conversation.entity import Conversation
from arc.domain.todo.value_objects import ConversationPurpose, MessageRole


async def _aiter(events):
    """把事件列表包装成 async iterator,模拟 ExecutionEngine 事件流。"""
    for e in events:
        yield e


class TestConversationServiceDelegation:
    """验证 generate_response_stream / generate_response 委托 ExecutionEngine。"""

    def _make_svc(self, events, **param_overrides):
        """构造一个绕过 __init__ 的 ConversationService,mock 掉引擎与配置读取。"""
        svc = ConversationService.__new__(ConversationService)
        svc._engine = MagicMock()
        svc._engine.generate_response_stream = MagicMock(
            return_value=_aiter(events)
        )
        svc._get_project_local_path = AsyncMock(
            return_value=param_overrides.get("project_path", "/proj")
        )
        svc._get_sandbox_policy = AsyncMock(
            return_value=param_overrides.get("sandbox_policy", "policy")
        )
        svc._is_orchestration_enabled = AsyncMock(
            return_value=param_overrides.get("orchestration_enabled", True)
        )
        svc._get_llm_config = AsyncMock(
            return_value=param_overrides.get("llm_config", {"model": "x"})
        )
        return svc

    @pytest.mark.asyncio
    async def test_generate_response_stream_delegates_with_full_params(self):
        svc = self._make_svc([{"content": "hi"}, {"event": "tool_call"}])
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)

        chunks = [c async for c in svc.generate_response_stream(conv)]

        assert chunks == [{"content": "hi"}, {"event": "tool_call"}]
        svc._engine.generate_response_stream.assert_called_once()
        _, kwargs = svc._engine.generate_response_stream.call_args
        assert kwargs["project_path"] == "/proj"
        assert kwargs["sandbox_policy"] == "policy"
        assert kwargs["orchestration_enabled"] is True
        assert kwargs["llm_config"] == {"model": "x"}

    @pytest.mark.asyncio
    async def test_generate_response_stream_no_project_path_still_delegates(self):
        """无项目路径(text-only)时仍委托,project_path=None。"""
        svc = self._make_svc(
            [{"content": "ok"}],
            project_path=None,
            sandbox_policy=None,
            orchestration_enabled=False,
            llm_config=None,
        )
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)

        chunks = [c async for c in svc.generate_response_stream(conv)]

        assert chunks == [{"content": "ok"}]
        _, kwargs = svc._engine.generate_response_stream.call_args
        assert kwargs["project_path"] is None
        assert kwargs["orchestration_enabled"] is False

    @pytest.mark.asyncio
    async def test_generate_response_consumes_stream_returns_last_message(self):
        """非流式 generate_response 消费 stream,返回 ExecutionEngine 写入的最后 assistant 消息。"""
        svc = self._make_svc([{"content": "partial"}])
        conv = Conversation(todo_id=uuid.uuid4(), purpose=ConversationPurpose.CLARIFICATION)
        # 模拟 ExecutionEngine 在 stream 过程中 add_message 写入 assistant 消息
        conv.add_message(role=MessageRole.ASSISTANT, content="final answer")

        msg = await svc.generate_response(conv)

        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "final answer"
        svc._engine.generate_response_stream.assert_called_once()
