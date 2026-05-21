"""Integration tests for Claude Code adapter — tests the adapter lifecycle
using a mock subprocess to simulate the claude CLI."""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from arc.application.agent.adapters.claude_code import ClaudeCodeAdapter
from arc.application.agent.context_builder import TaskContext
from arc.domain.agent.value_objects import SessionStatus


@pytest.fixture
def adapter(tmp_path):
    script = tmp_path / "mock_claude"
    script.write_text(
        '#!/bin/sh\n'
        'read input\n'
        'echo \'{"result": "task completed", "type": "result"}\'\n'
    )
    script.chmod(0o755)
    return ClaudeCodeAdapter(cli_path=str(script), work_dir=str(tmp_path))


@pytest.fixture
def failing_adapter(tmp_path):
    script = tmp_path / "mock_claude_fail"
    script.write_text(
        '#!/bin/sh\n'
        'echo \'{"type": "error", "message": "something went wrong"}\' >&2\n'
        'exit 1\n'
    )
    script.chmod(0o755)
    return ClaudeCodeAdapter(cli_path=str(script), work_dir=str(tmp_path))


@pytest.fixture
def slow_adapter(tmp_path):
    script = tmp_path / "mock_claude_slow"
    script.write_text(
        '#!/bin/sh\n'
        'read input\n'
        'sleep 60\n'
    )
    script.chmod(0o755)
    return ClaudeCodeAdapter(cli_path=str(script), work_dir=str(tmp_path))


@pytest.fixture
def context():
    return TaskContext(
        todo_id=str(uuid.uuid4()),
        todo_title="Test Task",
        todo_description="Implement a feature",
    )


@pytest.mark.anyio
async def test_start_returns_session_id(adapter, context):
    session_id = await adapter.start(context)
    assert session_id
    assert isinstance(session_id, str)
    uuid.UUID(session_id)
    await adapter.close()


@pytest.mark.anyio
async def test_lifecycle_success(adapter, context):
    session_id = await adapter.start(context)

    await asyncio.sleep(0.5)

    status = await adapter.get_status(session_id)
    assert status in (SessionStatus.RUNNING, SessionStatus.COMPLETED)

    for _ in range(20):
        status = await adapter.get_status(session_id)
        if status == SessionStatus.COMPLETED:
            break
        await asyncio.sleep(0.2)

    assert status == SessionStatus.COMPLETED

    events = await adapter.get_events(session_id)
    assert len(events) > 0
    assert any("task completed" in e.content for e in events)

    await adapter.close()


@pytest.mark.anyio
async def test_lifecycle_error(failing_adapter, context):
    session_id = await failing_adapter.start(context)

    for _ in range(20):
        status = await failing_adapter.get_status(session_id)
        if status != SessionStatus.RUNNING:
            break
        await asyncio.sleep(0.2)

    assert status == SessionStatus.ERROR
    await failing_adapter.close()


@pytest.mark.anyio
async def test_cancel(slow_adapter, context):
    session_id = await slow_adapter.start(context)
    await asyncio.sleep(0.3)

    status = await slow_adapter.get_status(session_id)
    assert status == SessionStatus.RUNNING

    await slow_adapter.cancel(session_id)

    status = await slow_adapter.get_status(session_id)
    assert status in (SessionStatus.ERROR, SessionStatus.COMPLETED)

    await slow_adapter.close()


@pytest.mark.anyio
async def test_get_events_incremental(adapter, context):
    session_id = await adapter.start(context)

    for _ in range(20):
        if (await adapter.get_status(session_id)) == SessionStatus.COMPLETED:
            break
        await asyncio.sleep(0.2)

    events1 = await adapter.get_events(session_id)
    assert len(events1) > 0

    last_id = events1[-1].event_id
    events2 = await adapter.get_events(session_id, since=last_id)
    assert len(events2) == 0

    await adapter.close()


@pytest.mark.anyio
async def test_unknown_session():
    adapter = ClaudeCodeAdapter(cli_path="claude")
    status = await adapter.get_status("nonexistent")
    assert status == SessionStatus.ERROR

    events = await adapter.get_events("nonexistent")
    assert events == []

    await adapter.cancel("nonexistent")
    await adapter.close()
