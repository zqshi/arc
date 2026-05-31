"""Hook Manager — Harness §12 Hooks/Middleware.

7 注入点的事件驱动 Hook 管道。

注入点:
1. pre_input  — 用户消息进入前
2. pre_llm    — LLM 推理前（可修改 prompt）
3. post_llm   — LLM 响应后（可过滤/审计）
4. pre_tool   — 工具调用前（可修改参数）
5. post_tool  — 工具执行后（可过滤结果）
6. pre_response — 响应发送给用户前
7. post_response — 响应发送后（审计/通知）

设计原则:
- Hook 失败不影响主流程（与 Middleware 不同）
- 每个 Hook 有独立超时（默认 5s）
- 按注册顺序执行，前一个的输出是后一个的输入
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from enum import StrEnum
from typing import Callable, Coroutine

logger = logging.getLogger(__name__)

DEFAULT_HOOK_TIMEOUT = 5.0  # seconds


class HookPoint(StrEnum):
    """Hook 注入点枚举。"""

    PRE_INPUT = "pre_input"
    PRE_LLM = "pre_llm"
    POST_LLM = "post_llm"
    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    PRE_RESPONSE = "pre_response"
    POST_RESPONSE = "post_response"


# Hook 函数签名: async (context: dict) -> dict
HookFn = Callable[[dict], Coroutine[None, None, dict]]


class HookManager:
    """事件驱动的 Hook 管道管理器。

    Usage:
        manager = HookManager()
        manager.register(HookPoint.PRE_TOOL, audit_hook)
        context = await manager.trigger(HookPoint.PRE_TOOL, {"tool": "bash", "params": {...}})
    """

    def __init__(self, timeout: float = DEFAULT_HOOK_TIMEOUT):
        self._hooks: dict[HookPoint, list[HookFn]] = defaultdict(list)
        self._timeout = timeout

    def register(self, point: HookPoint, hook: HookFn) -> None:
        """注册 hook 到指定注入点。"""
        self._hooks[point].append(hook)
        logger.debug("Hook registered at %s: %s", point, hook.__name__)

    async def trigger(self, point: HookPoint, context: dict) -> dict:
        """触发指定注入点的所有 hook。

        按注册顺序执行，每个 hook 可修改 context。
        单个 hook 失败不影响后续 hook 和主流程。

        Returns:
            可能被 hook 修改过的 context。
        """
        hooks = self._hooks.get(point, [])
        if not hooks:
            return context

        for hook in hooks:
            try:
                result = await asyncio.wait_for(
                    hook(context),
                    timeout=self._timeout,
                )
                if isinstance(result, dict):
                    context = result
            except asyncio.TimeoutError:
                logger.warning(
                    "Hook %s at %s timed out (%.1fs)",
                    hook.__name__, point, self._timeout,
                )
            except Exception as exc:
                logger.warning(
                    "Hook %s at %s failed: %s",
                    hook.__name__, point, exc,
                )
                # Hook 失败不阻断主流程

        return context

    def unregister_all(self, point: HookPoint | None = None) -> None:
        """移除所有 hook（可选指定注入点）。"""
        if point is None:
            self._hooks.clear()
        else:
            self._hooks.pop(point, None)

    @property
    def registered_count(self) -> dict[str, int]:
        """各注入点已注册的 hook 数量。"""
        return {k.value: len(v) for k, v in self._hooks.items() if v}
