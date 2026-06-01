"""Tests for application/sandbox runtime — ApprovalGateSandboxRuntime."""

import asyncio
import uuid

import pytest

from arc.application.sandbox.runtime import ApprovalGateSandboxRuntime
from arc.domain.sandbox.value_objects import SandboxPolicy, SandboxMode


def _make_runtime():
    policy = SandboxPolicy(
        mode=SandboxMode.APPROVAL_GATE,
        approval_required_for=["run_command", "write_file"],
    )
    return ApprovalGateSandboxRuntime(policy=policy, project_path="/tmp/test")


class TestApprovalGateSandboxRuntime:
    def test_creation(self):
        rt = _make_runtime()
        assert rt is not None

    @pytest.mark.asyncio
    async def test_respond_unknown_request(self):
        rt = _make_runtime()
        result = rt.respond("nonexistent-id", True)
        assert result is False

    @pytest.mark.asyncio
    async def test_respond_resolves_future(self):
        rt = _make_runtime()
        req_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        rt._pending[req_id] = future

        rt.respond(req_id, True)
        assert future.done()
        assert future.result() is True

    @pytest.mark.asyncio
    async def test_respond_deny(self):
        rt = _make_runtime()
        req_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        rt._pending[req_id] = future

        rt.respond(req_id, False)
        assert future.result() is False

    @pytest.mark.asyncio
    async def test_close(self):
        rt = _make_runtime()
        await rt.close()

