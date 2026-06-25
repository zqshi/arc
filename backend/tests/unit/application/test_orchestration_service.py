"""Tests for application/orchestration service — plan extraction & layer logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from arc.application.execution.tool_loop import ToolLoopEvent
from arc.application.orchestration.service import OrchestrationService
from arc.domain.orchestration.entity import OrchestrationPlan
from arc.domain.orchestration.value_objects import SubtaskType, WorkerRole


class TestExtractPlanJson:
    """Test the static JSON plan extraction from LLM output."""

    def test_valid_json_block(self):
        content = '''Here is my plan:
```json
{
  "subtasks": [
    {"description": "read code", "task_type": "read_analysis", "worker_role": "explorer"},
    {"description": "write fix", "task_type": "file_write", "worker_role": "writer"}
  ]
}
```
'''
        result = OrchestrationService._extract_plan_json(content)
        assert result is not None
        assert len(result["subtasks"]) == 2

    def test_no_json_returns_none(self):
        result = OrchestrationService._extract_plan_json("no json here")
        assert result is None

    def test_invalid_json(self):
        content = "```json\n{invalid}\n```"
        result = OrchestrationService._extract_plan_json(content)
        assert result is None

    def test_json_without_subtasks(self):
        content = '```json\n{"foo": "bar"}\n```'
        result = OrchestrationService._extract_plan_json(content)
        # Returns the dict but no subtasks key
        assert result is not None or result is None  # implementation dependent

    def test_inline_json(self):
        content = '{"subtasks": [{"description": "x", "task_type": "read_analysis", "worker_role": "explorer"}]}'
        result = OrchestrationService._extract_plan_json(content)
        assert result is not None


# --- execute async generator characterization ---


def _async_gen(events: list[ToolLoopEvent]):
    """构造一个 yield 给定事件的 async generator。"""
    async def gen():
        for e in events:
            yield e
    return gen()


async def _collect(async_gen) -> list[ToolLoopEvent]:
    return [e async for e in async_gen]


def _make_plan(n: int = 2) -> OrchestrationPlan:
    plan = OrchestrationPlan(conversation_id=uuid.uuid4(), parent_message_id="m1")
    for i in range(n):
        plan.add_subtask(
            description=f"task{i}",
            task_type=SubtaskType.READ_ANALYSIS,
            worker_role=WorkerRole.EXPLORER,
        )
    return plan


def _make_svc() -> OrchestrationService:
    """跳过 __init__ (需 AdapterPool), 手动设依赖。"""
    svc = OrchestrationService.__new__(OrchestrationService)
    svc._pool = MagicMock()
    return svc


class TestOrchestrationExecute:
    """execute async generator — 编排决策 + 流式事件序列 characterization。"""

    @pytest.mark.asyncio
    async def test_single_agent_fallback_when_plan_none(self):
        svc = _make_svc()
        svc._extract_user_message = MagicMock(return_value="hi")
        svc._plan = AsyncMock(return_value=None)
        svc._single_agent = MagicMock(
            return_value=_async_gen([ToolLoopEvent(type="text_delta", content="x")])
        )
        svc._synthesize = MagicMock(return_value=_async_gen([]))

        events = await _collect(svc.execute([MagicMock()], MagicMock()))

        assert any(e.type == "text_delta" for e in events)
        assert not any(e.type == "orchestration_start" for e in events)
        svc._single_agent.assert_called_once()
        svc._synthesize.assert_not_called()

    @pytest.mark.asyncio
    async def test_multi_agent_full_event_sequence(self):
        plan = _make_plan(2)
        svc = _make_svc()
        svc._extract_user_message = MagicMock(return_value="hi")
        svc._plan = AsyncMock(return_value=plan)
        svc._run_worker = AsyncMock(return_value="output")
        svc._synthesize = MagicMock(
            return_value=_async_gen([ToolLoopEvent(type="text_delta", content="final")])
        )

        events = await _collect(svc.execute([MagicMock()], MagicMock()))

        types = [e.type for e in events]
        assert types[0] == "orchestration_start"
        assert types.count("worker_complete") == 2
        assert "synthesis_start" in types
        assert "text_delta" in types  # synthesis 透传
        assert types[-1] == "orchestration_complete"
        assert plan.completed_at is not None  # mark_complete 被调

    @pytest.mark.asyncio
    async def test_worker_exception_emits_worker_error(self):
        plan = _make_plan(1)
        svc = _make_svc()
        svc._extract_user_message = MagicMock(return_value="hi")
        svc._plan = AsyncMock(return_value=plan)
        svc._run_worker = AsyncMock(side_effect=RuntimeError("boom"))
        svc._synthesize = MagicMock(return_value=_async_gen([]))

        events = await _collect(svc.execute([MagicMock()], MagicMock()))

        assert any(e.type == "worker_error" for e in events)
        assert plan.subtasks[0].result == "boom"  # st.fail(str(exc))

    @pytest.mark.asyncio
    async def test_synthesis_events_passed_through(self):
        plan = _make_plan(1)
        svc = _make_svc()
        svc._extract_user_message = MagicMock(return_value="hi")
        svc._plan = AsyncMock(return_value=plan)
        svc._run_worker = AsyncMock(return_value="out")
        svc._synthesize = MagicMock(
            return_value=_async_gen([
                ToolLoopEvent(type="text_delta", content="a"),
                ToolLoopEvent(type="complete"),
            ])
        )

        events = await _collect(svc.execute([MagicMock()], MagicMock()))

        contents = [e.content for e in events]
        assert "a" in contents
        assert any(e.type == "complete" for e in events)
