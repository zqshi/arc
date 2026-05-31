"""四级验证链 — Harness §9 Verify Loop.

L1 语法: JSON/代码块格式校验 (< 1s)
L2 语义: 交付物必要字段检查 (< 1s)
L3 集成: lint/type-check（可选，需 project_path）(1-5s)
L4 意图: LLM 自审 "输出是否回答了用户问题？" (2-5s)

每级失败 → 返回 VerifyResult，调用方按严重程度分级响应。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc.application.ai.llm_adapter import LLMAdapter

logger = logging.getLogger(__name__)

# 从 agent_loop.py 复用的交付物字段定义
DELIVERABLE_REQUIRED_FIELDS: dict[str, list[str]] = {
    "requirement_spec": ["background", "user_stories", "acceptance_criteria", "boundaries"],
    "interaction_design": ["user_flows", "page_map"],
    "ui_spec": ["design_tokens", "component_specs"],
    "prototype": ["pages"],
    "tech_architecture": ["data_model", "api_design", "tech_decisions"],
    "dev_report": ["test_design", "implementation", "validation"],
    "test_report": ["criteria_verification"],
    "experience_card": ["problem", "solution", "decisions"],
}

_DELIVERABLE_RE = re.compile(
    r"\[DELIVERABLE:(\w+)\]\s*```(?:json)?\s*(.*?)```",
    re.DOTALL,
)


@dataclass
class VerifyContext:
    """验证所需的上下文信息。"""

    content: str
    user_intent: str = ""
    project_path: str | None = None
    deliverable_type: str | None = None


@dataclass
class VerifyResult:
    """验证结果。"""

    passed: bool
    level: str  # L1/L2/L3/L4
    errors: list[str] = field(default_factory=list)
    suggestion: str = ""


class VerifyChain:
    """四级验证链。

    按严重程度递进检查，任何一级失败即返回。
    L1/L2 失败 → 建议自动重试
    L3 失败 → 建议回退
    L4 失败 → 建议请求用户确认
    """

    def __init__(self, adapter: LLMAdapter | None = None):
        self._adapter = adapter

    async def verify(self, ctx: VerifyContext) -> VerifyResult:
        """执行四级验证链。"""
        # L1: 语法检查
        result = self._check_syntax(ctx)
        if not result.passed:
            return result

        # L2: 语义检查
        result = self._check_semantics(ctx)
        if not result.passed:
            return result

        # L3: 集成检查（可选）
        if ctx.project_path:
            result = await self._check_integration(ctx)
            if not result.passed:
                return result

        # L4: 意图检查（需要 LLM）
        if self._adapter and ctx.user_intent:
            result = await self._check_intent(ctx)
            if not result.passed:
                return result

        return VerifyResult(passed=True, level="ALL")

    # ------------------------------------------------------------------
    # L1: 语法检查
    # ------------------------------------------------------------------

    @staticmethod
    def _check_syntax(ctx: VerifyContext) -> VerifyResult:
        """检查 JSON 可解析性、代码块闭合。"""
        errors: list[str] = []

        # 检查 DELIVERABLE 块的 JSON 可解析性
        for match in _DELIVERABLE_RE.finditer(ctx.content):
            dtype = match.group(1)
            json_text = match.group(2).strip()
            try:
                json.loads(json_text)
            except json.JSONDecodeError as e:
                errors.append(
                    f"交付物 [{dtype}] JSON 解析失败: {e.msg} (行 {e.lineno})"
                )

        # 检查代码块闭合
        backtick_count = ctx.content.count("```")
        if backtick_count % 2 != 0:
            errors.append(f"代码块未闭合: 发现 {backtick_count} 个 ``` 标记（应为偶数）")

        # 检查大括号配对
        open_braces = ctx.content.count("{") - ctx.content.count("}")
        if abs(open_braces) > 3:
            errors.append(f"大括号不配对: 差值 {open_braces}")

        if errors:
            return VerifyResult(
                passed=False, level="L1", errors=errors,
                suggestion="格式有误，请修正 JSON 格式或闭合代码块后重试。",
            )
        return VerifyResult(passed=True, level="L1")

    # ------------------------------------------------------------------
    # L2: 语义检查
    # ------------------------------------------------------------------

    @staticmethod
    def _check_semantics(ctx: VerifyContext) -> VerifyResult:
        """检查交付物必要字段是否存在。"""
        errors: list[str] = []

        for match in _DELIVERABLE_RE.finditer(ctx.content):
            dtype = match.group(1)
            json_text = match.group(2).strip()

            required = DELIVERABLE_REQUIRED_FIELDS.get(dtype, [])
            if not required:
                continue

            try:
                data = json.loads(json_text)
            except json.JSONDecodeError:
                continue  # L1 已经报告

            if not isinstance(data, dict):
                errors.append(f"[{dtype}] 期望 JSON 对象，得到 {type(data).__name__}")
                continue

            missing = [f for f in required if f not in data or not data[f]]
            if missing:
                errors.append(
                    f"[{dtype}] 缺少必要字段: {', '.join(missing)}"
                )

        if errors:
            return VerifyResult(
                passed=False, level="L2", errors=errors,
                suggestion="交付物缺少必要字段，请补充后重试。",
            )
        return VerifyResult(passed=True, level="L2")

    # ------------------------------------------------------------------
    # L3: 集成检查
    # ------------------------------------------------------------------

    @staticmethod
    async def _check_integration(ctx: VerifyContext) -> VerifyResult:
        """运行 lint/type-check（如果可用）。"""
        import asyncio

        if not ctx.project_path:
            return VerifyResult(passed=True, level="L3")

        errors: list[str] = []

        # 提取内容中提到的 Python 文件
        py_files = re.findall(r'["\']([^"\']+\.py)["\']', ctx.content)
        if not py_files:
            return VerifyResult(passed=True, level="L3")

        # 对前 3 个文件尝试 py_compile 检查
        from pathlib import Path

        for fpath in py_files[:3]:
            full_path = Path(ctx.project_path) / fpath
            if not full_path.exists():
                continue
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python", "-m", "py_compile", str(full_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
                if proc.returncode != 0:
                    errors.append(f"{fpath}: {stderr.decode().strip()}")
            except (asyncio.TimeoutError, FileNotFoundError):
                pass

        if errors:
            return VerifyResult(
                passed=False, level="L3", errors=errors,
                suggestion="代码存在语法错误，请修正。",
            )
        return VerifyResult(passed=True, level="L3")

    # ------------------------------------------------------------------
    # L4: 意图检查
    # ------------------------------------------------------------------

    async def _check_intent(self, ctx: VerifyContext) -> VerifyResult:
        """LLM 自审：输出是否回答了用户问题？"""
        if not self._adapter:
            return VerifyResult(passed=True, level="L4")

        from arc.application.ai.llm_adapter import LLMMessage

        try:
            prompt = (
                f"用户的问题/请求是：\n{ctx.user_intent}\n\n"
                f"AI 的输出是（前 2000 字）：\n{ctx.content[:2000]}\n\n"
                "请判断：这个输出是否有效地回答/满足了用户的请求？\n"
                "回答 YES 或 NO，然后一句话解释原因。"
            )
            response = await self._adapter.chat(
                [
                    LLMMessage(role="system", content="你是一个输出质量审查员。"),
                    LLMMessage(role="user", content=prompt),
                ],
                temperature=0.1,
                max_tokens=256,
            )
            answer = response.content.strip().upper()
            if answer.startswith("NO"):
                return VerifyResult(
                    passed=False, level="L4",
                    errors=[f"意图不匹配: {response.content.strip()}"],
                    suggestion="输出可能未回答用户问题，建议用户确认。",
                )
        except Exception as exc:
            logger.warning("L4 intent check failed: %s", exc)

        return VerifyResult(passed=True, level="L4")
