"""Unit tests for HookManager."""

from __future__ import annotations

import asyncio

import pytest

from arc.application.hooks.manager import HookManager, HookPoint


class TestHookRegistration:
    def test_register_hook(self) -> None:
        manager = HookManager()

        async def my_hook(ctx: dict) -> dict:
            return ctx

        manager.register(HookPoint.PRE_TOOL, my_hook)
        assert manager.registered_count == {"pre_tool": 1}

    def test_register_multiple_hooks(self) -> None:
        manager = HookManager()

        async def hook_a(ctx: dict) -> dict:
            return ctx

        async def hook_b(ctx: dict) -> dict:
            return ctx

        manager.register(HookPoint.PRE_TOOL, hook_a)
        manager.register(HookPoint.PRE_TOOL, hook_b)
        assert manager.registered_count == {"pre_tool": 2}

    def test_unregister_all(self) -> None:
        manager = HookManager()

        async def hook(ctx: dict) -> dict:
            return ctx

        manager.register(HookPoint.PRE_TOOL, hook)
        manager.register(HookPoint.POST_TOOL, hook)
        manager.unregister_all()
        assert manager.registered_count == {}

    def test_unregister_specific_point(self) -> None:
        manager = HookManager()

        async def hook(ctx: dict) -> dict:
            return ctx

        manager.register(HookPoint.PRE_TOOL, hook)
        manager.register(HookPoint.POST_TOOL, hook)
        manager.unregister_all(HookPoint.PRE_TOOL)
        assert manager.registered_count == {"post_tool": 1}


class TestHookTrigger:
    @pytest.mark.asyncio
    async def test_trigger_no_hooks(self) -> None:
        manager = HookManager()
        ctx = {"key": "value"}
        result = await manager.trigger(HookPoint.PRE_INPUT, ctx)
        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_hook_modifies_context(self) -> None:
        manager = HookManager()

        async def add_flag(ctx: dict) -> dict:
            ctx["flagged"] = True
            return ctx

        manager.register(HookPoint.PRE_TOOL, add_flag)
        result = await manager.trigger(HookPoint.PRE_TOOL, {"data": 1})
        assert result["flagged"] is True
        assert result["data"] == 1

    @pytest.mark.asyncio
    async def test_hooks_chain_in_order(self) -> None:
        manager = HookManager()
        call_order = []

        async def hook_a(ctx: dict) -> dict:
            call_order.append("a")
            ctx["value"] = ctx.get("value", 0) + 1
            return ctx

        async def hook_b(ctx: dict) -> dict:
            call_order.append("b")
            ctx["value"] = ctx.get("value", 0) * 2
            return ctx

        manager.register(HookPoint.PRE_LLM, hook_a)
        manager.register(HookPoint.PRE_LLM, hook_b)
        result = await manager.trigger(HookPoint.PRE_LLM, {"value": 0})

        assert call_order == ["a", "b"]
        assert result["value"] == 2  # (0 + 1) * 2

    @pytest.mark.asyncio
    async def test_hook_failure_isolated(self) -> None:
        """A failing hook should not affect subsequent hooks."""
        manager = HookManager()

        async def failing_hook(ctx: dict) -> dict:
            raise ValueError("boom")

        async def good_hook(ctx: dict) -> dict:
            ctx["good"] = True
            return ctx

        manager.register(HookPoint.POST_TOOL, failing_hook)
        manager.register(HookPoint.POST_TOOL, good_hook)
        result = await manager.trigger(HookPoint.POST_TOOL, {})

        # good_hook still ran despite failing_hook
        assert result["good"] is True

    @pytest.mark.asyncio
    async def test_hook_timeout(self) -> None:
        """A slow hook should be timed out without blocking."""
        manager = HookManager(timeout=0.1)

        async def slow_hook(ctx: dict) -> dict:
            await asyncio.sleep(5)
            ctx["slow"] = True
            return ctx

        async def fast_hook(ctx: dict) -> dict:
            ctx["fast"] = True
            return ctx

        manager.register(HookPoint.PRE_RESPONSE, slow_hook)
        manager.register(HookPoint.PRE_RESPONSE, fast_hook)
        result = await manager.trigger(HookPoint.PRE_RESPONSE, {})

        assert "slow" not in result
        assert result["fast"] is True

    @pytest.mark.asyncio
    async def test_hook_returning_none_preserves_context(self) -> None:
        """If a hook returns None instead of dict, context is unchanged."""
        manager = HookManager()

        async def bad_return(ctx: dict) -> dict:
            return None  # type: ignore

        manager.register(HookPoint.POST_LLM, bad_return)
        result = await manager.trigger(HookPoint.POST_LLM, {"original": True})
        assert result["original"] is True
