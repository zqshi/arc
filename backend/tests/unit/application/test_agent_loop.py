"""Tests for the AgentLoop engine."""

from __future__ import annotations

import asyncio

import pytest

from arc.application.ai.llm_adapter import LLMAdapter, LLMMessage, LLMResponse, StreamResult
from arc.application.execution.agent_loop import (
    AgentLoop,
    DeliverableValidator,
    LoopConfig,
)


class FakeAdapter(LLMAdapter):
    """Controllable adapter for testing AgentLoop behavior."""

    def __init__(self, responses: list[tuple[str, str]]):
        """responses: list of (content, finish_reason) pairs, one per iteration."""
        self._responses = list(responses)
        self._call_count = 0

    async def chat(self, messages, *, temperature=0.7, max_tokens=4096):
        return LLMResponse(content="", model="test")

    async def chat_stream(self, messages, *, temperature=0.7, max_tokens=4096):
        content, _ = self._responses[min(self._call_count, len(self._responses) - 1)]
        for char in content:
            yield char

    async def chat_stream_with_result(self, messages, *, temperature=0.7, max_tokens=4096):
        idx = min(self._call_count, len(self._responses) - 1)
        content, finish_reason = self._responses[idx]
        self._call_count += 1
        result = StreamResult(
            finish_reason=finish_reason,
            model="test",
            usage={"completion_tokens": len(content)},
        )

        async def _gen():
            for char in content:
                yield char

        return _gen(), result

    async def embed(self, text):
        return [0.0] * 384

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_normal_completion():
    adapter = FakeAdapter([("Hello, world!", "stop")])
    loop = AgentLoop(adapter, LoopConfig(max_continuations=3))

    events = []
    async for event in loop.run([LLMMessage(role="user", content="hi")]):
        events.append(event)

    complete_events = [e for e in events if e.type == "complete"]
    assert len(complete_events) == 1
    assert complete_events[0].content == "Hello, world!"
    assert loop.metrics.continuations == 0
    assert loop.metrics.final_state == "complete"


@pytest.mark.asyncio
async def test_truncation_then_continuation():
    adapter = FakeAdapter([
        ("First part of the response...", "length"),
        (" and here is the rest.", "stop"),
    ])
    loop = AgentLoop(adapter, LoopConfig(max_continuations=3))

    events = []
    async for event in loop.run([LLMMessage(role="user", content="hi")]):
        events.append(event)

    continuation_events = [e for e in events if e.type == "continuation"]
    complete_events = [e for e in events if e.type == "complete"]
    assert len(continuation_events) == 1
    assert len(complete_events) == 1
    assert complete_events[0].content == "First part of the response... and here is the rest."
    assert loop.metrics.continuations == 1
    assert loop.metrics.iterations == 2


@pytest.mark.asyncio
async def test_max_continuations_respected():
    adapter = FakeAdapter([
        ("chunk1", "length"),
        ("chunk2", "length"),
        ("chunk3", "length"),
        ("chunk4", "length"),
    ])
    config = LoopConfig(max_continuations=2)
    loop = AgentLoop(adapter, config)

    events = []
    async for event in loop.run([LLMMessage(role="user", content="hi")]):
        events.append(event)

    assert loop.metrics.continuations == 2
    assert loop.metrics.iterations == 3
    complete = [e for e in events if e.type == "complete"]
    assert len(complete) == 1


@pytest.mark.asyncio
async def test_heuristic_truncation_detection():
    adapter = FakeAdapter([
        ('{"data": {', "stop"),
        ('"value": 1}}', "stop"),
    ])
    loop = AgentLoop(adapter, LoopConfig(max_continuations=3))

    events = []
    async for event in loop.run([LLMMessage(role="user", content="hi")]):
        events.append(event)

    assert loop.metrics.continuations == 1
    complete = [e for e in events if e.type == "complete"]
    assert complete[0].content == '{"data": {"value": 1}}'


@pytest.mark.asyncio
async def test_validation_retry():
    bad_json = '[DELIVERABLE:requirement_spec]\n```json\n{"background": "test"}\n```'
    good_json = (
        '[DELIVERABLE:requirement_spec]\n```json\n'
        '{"background": "test", "user_stories": [], '
        '"acceptance_criteria": [], "boundaries": {}}\n```'
    )

    adapter = FakeAdapter([
        (bad_json, "stop"),
        (good_json, "stop"),
    ])
    validator = DeliverableValidator({
        "requirement_spec": ["background", "user_stories", "acceptance_criteria", "boundaries"],
    })
    loop = AgentLoop(adapter, LoopConfig(max_validation_retries=2))

    events = []
    async for event in loop.run(
        [LLMMessage(role="user", content="hi")],
        validator=validator,
    ):
        events.append(event)

    assert loop.metrics.validation_retries == 1
    retry_events = [e for e in events if e.type == "validation_retry"]
    assert len(retry_events) == 1


@pytest.mark.asyncio
async def test_validation_exhausted():
    bad_json = '[DELIVERABLE:requirement_spec]\n```json\n{"background": "test"}\n```'
    adapter = FakeAdapter([
        (bad_json, "stop"),
        (bad_json, "stop"),
        (bad_json, "stop"),
    ])
    validator = DeliverableValidator({
        "requirement_spec": ["background", "user_stories", "acceptance_criteria", "boundaries"],
    })
    loop = AgentLoop(adapter, LoopConfig(max_validation_retries=2))

    events = []
    async for event in loop.run(
        [LLMMessage(role="user", content="hi")],
        validator=validator,
    ):
        events.append(event)

    assert loop.metrics.validation_retries == 2
    complete = [e for e in events if e.type == "complete"]
    assert len(complete) == 1


@pytest.mark.asyncio
async def test_budget_exceeded():
    long_text = "x" * 1000
    adapter = FakeAdapter([
        (long_text, "length"),
        (long_text, "length"),
    ])
    config = LoopConfig(
        max_continuations=5,
        token_budget=500,
    )
    loop = AgentLoop(adapter, config)

    events = []
    async for event in loop.run([LLMMessage(role="user", content="hi")]):
        events.append(event)

    budget_events = [e for e in events if e.type == "budget_warning"]
    assert len(budget_events) == 1
    assert loop.metrics.final_state == "budget_exceeded"


@pytest.mark.asyncio
async def test_timeout():
    class SlowAdapter(FakeAdapter):
        async def chat_stream_with_result(self, messages, *, temperature=0.7, max_tokens=4096):
            result = StreamResult(finish_reason="stop", model="test")

            async def _slow():
                for i in range(100):
                    await asyncio.sleep(0.05)
                    yield f"chunk{i}"

            return _slow(), result

    adapter = SlowAdapter([("", "stop")])
    config = LoopConfig(wall_timeout_seconds=0.1)
    loop = AgentLoop(adapter, config)

    events = []
    async for event in loop.run([LLMMessage(role="user", content="hi")]):
        events.append(event)

    assert loop.metrics.final_state == "timed_out"


@pytest.mark.asyncio
async def test_metrics_populated():
    adapter = FakeAdapter([("Response content", "stop")])
    loop = AgentLoop(adapter)

    async for _ in loop.run([LLMMessage(role="user", content="hi")]):
        pass

    m = loop.metrics
    assert m.loop_id
    assert m.iterations == 1
    assert m.continuations == 0
    assert m.total_tokens > 0
    assert m.elapsed_ms >= 0
    assert m.final_state == "complete"
    assert m.finish_reasons == ["stop"]


class TestDeliverableValidator:
    def test_no_deliverables(self):
        v = DeliverableValidator({"requirement_spec": ["background"]})
        assert v.validate("Just a normal response") is None

    def test_valid_deliverable(self):
        content = '[DELIVERABLE:requirement_spec]\n```json\n{"background": "test"}\n```'
        v = DeliverableValidator({"requirement_spec": ["background"]})
        assert v.validate(content) is None

    def test_missing_fields(self):
        content = '[DELIVERABLE:requirement_spec]\n```json\n{"background": "test"}\n```'
        v = DeliverableValidator({"requirement_spec": ["background", "user_stories"]})
        errors = v.validate(content)
        assert errors is not None
        assert "user_stories" in errors

    def test_invalid_json(self):
        content = '[DELIVERABLE:requirement_spec]\n```json\n{bad json}\n```'
        v = DeliverableValidator({"requirement_spec": ["background"]})
        errors = v.validate(content)
        assert errors is not None
        assert "JSON" in errors

    def test_multiple_deliverables(self):
        content = (
            '[DELIVERABLE:requirement_spec]\n```json\n{"background": "test"}\n```\n\n'
            '[DELIVERABLE:ui_design]\n```json\n{"flow_diagram": "graph TD"}\n```'
        )
        v = DeliverableValidator({
            "requirement_spec": ["background"],
            "ui_design": ["flow_diagram", "wireframes"],
        })
        errors = v.validate(content)
        assert errors is not None
        assert "wireframes" in errors
        assert "requirement_spec" not in errors
