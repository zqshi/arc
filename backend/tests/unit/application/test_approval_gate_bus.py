"""ApprovalGateSandboxRuntime 审批链路测试 (v6.7 波次2)。

验证审批事件经 EventBus 跨 worker 路由: runtime 监听 bus channel
arc:sandbox:{cid}, 前端响应经 bus 投递, 持有 runtime 的 worker 本地
解析 asyncio.Future (future 不可跨进程)。
"""

from __future__ import annotations

import asyncio

import pytest

from arc.application.sandbox.runtime import ApprovalGateSandboxRuntime
from arc.domain.sandbox.value_objects import SandboxMode, SandboxPolicy
from arc.infrastructure.eventbus import InMemoryEventBus, set_global_bus

_CHANNEL_PREFIX = "arc:sandbox:"


@pytest.fixture
async def bus():
    b = InMemoryEventBus()
    set_global_bus(b)
    yield b
    set_global_bus(None)
    await b.shutdown()


class TestApprovalBusRouting:
    @pytest.mark.asyncio
    async def test_approval_response_via_bus_resolves_future(self, bus):
        """前端审批响应经 bus 路由到 runtime, 解析 pending future。"""
        captured: list[dict] = []

        async def emit(ev):
            captured.append(ev)

        policy = SandboxPolicy(mode=SandboxMode.APPROVAL_GATE)
        runtime = ApprovalGateSandboxRuntime(
            policy, "/tmp", conversation_id="conv-1", emit_callback=emit
        )

        # 启动审批请求 (创建 future + 启动 bus 监听)
        task = asyncio.create_task(
            runtime._request_approval("write_file", {"path": "x"})
        )
        await asyncio.sleep(0.15)  # 让 emit + monitor 就位

        # emit 应已发出 approval_required 事件 (含 request_id)
        assert captured, "approval_required 事件未发出"
        request_id = captured[0]["request_id"]

        # 模拟前端响应经 bus 投递 (跨 worker 路由)
        await bus.publish(
            _CHANNEL_PREFIX + "conv-1",
            {"request_id": request_id, "approved": True},
        )

        result = await asyncio.wait_for(task, timeout=2.0)
        assert result is True  # 批准 → _request_approval 返回 True
        await runtime.close()

    @pytest.mark.asyncio
    async def test_rejection_via_bus_returns_false(self, bus):
        """前端拒绝经 bus 路由, _request_approval 返回 False。"""
        captured: list[dict] = []

        async def emit(ev):
            captured.append(ev)

        policy = SandboxPolicy(mode=SandboxMode.APPROVAL_GATE)
        runtime = ApprovalGateSandboxRuntime(
            policy, "/tmp", conversation_id="conv-2", emit_callback=emit
        )

        task = asyncio.create_task(
            runtime._request_approval("run_command", {"command": "rm -rf /"})
        )
        await asyncio.sleep(0.15)
        request_id = captured[0]["request_id"]

        await bus.publish(
            _CHANNEL_PREFIX + "conv-2",
            {"request_id": request_id, "approved": False},
        )

        result = await asyncio.wait_for(task, timeout=2.0)
        assert result is False  # 拒绝
        await runtime.close()

    @pytest.mark.asyncio
    async def test_emit_callback_sends_approval_required(self, bus):
        """emit_callback 发出含 request_id/tool_name/tool_input 的事件。"""
        captured: list[dict] = []

        async def emit(ev):
            captured.append(ev)

        policy = SandboxPolicy(mode=SandboxMode.APPROVAL_GATE)
        runtime = ApprovalGateSandboxRuntime(
            policy, "/tmp", conversation_id="conv-3", emit_callback=emit
        )

        task = asyncio.create_task(
            runtime._request_approval("write_file", {"path": "a.txt", "content": "x"})
        )
        await asyncio.sleep(0.15)
        task.cancel()
        await runtime.close()

        assert len(captured) == 1
        ev = captured[0]
        assert ev["event"] == "approval_required"
        assert ev["tool_name"] == "write_file"
        assert "request_id" in ev
        assert ev["tool_input"]["path"] == "a.txt"
