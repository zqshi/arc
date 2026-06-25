"""Error Loop 检测 — Harness §5.4.

检测工具调用中的周期性重复模式（周期 2 或 3）。
用于识别 Agent 陷入 "相同错误 → 相同修复 → 相同错误" 的死循环。

v6.3 #9 (prompt-upgrade-plan): LCS 字符串相似度判循环升级为混合判断:
- 🟡 结构预筛: LCS 周期重复(签名完全相同/相似) → True (零 LLM)
- 🟢 LLM 语义确认: 窗口内有错误但 LCS 判否 → LLM 判"换工具犯同类错"
  (不同工具但同一类失败模式, LCS 判不出)
- 降级: LLM 失败/未注入 → False (回退 LCS 结果)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ERROR_LOOP_JUDGEMENT_PROMPT = """\
判断最近的工具调用是否在"换工具犯同类错"——用不同工具尝试但陷入同类错误循环。

[最近调用序列]
{recent_actions}

[输出契约] 仅输出 JSON, 不要其他内容:
{{"is_same_error_loop": <bool: 是否换工具犯同类错>, "confidence": <0-1>, "reason": <str>}}

判断: 不同工具调用是否重复同一类失败模式(权限/超时/路径/参数错误), 而非推进任务。
"""


@dataclass(frozen=True)
class ErrorLoopJudgement:
    """LLM 同类错误循环判断结果。"""

    is_same_error_loop: bool
    confidence: float
    reason: str = ""

    @classmethod
    def from_llm(cls, data: object) -> "ErrorLoopJudgement | None":
        """从 LLM 输出构造。缺 is_same_error_loop 或非 dict → None (降级信号)。"""
        if not isinstance(data, dict) or "is_same_error_loop" not in data:
            return None
        try:
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
        return cls(
            is_same_error_loop=bool(data["is_same_error_loop"]),
            confidence=confidence,
            reason=str(data.get("reason", "")),
        )


class ErrorLoopDetector:
    """死循环检测器。

    记录工具调用的 action signature（如 "tool_name:input_hash"），
    在滑动窗口内检测周期为 2 或 3 的重复模式 (LCS 结构预筛)；
    窗口内有错误时调 LLM 判断"换工具犯同类错" (语义确认)。
    """

    def __init__(
        self,
        window_size: int = 6,
        similarity_threshold: float = 0.85,
        *,
        llm_review_fn=None,
    ):
        self._window_size = window_size
        self._threshold = similarity_threshold
        # (action_signature, error_summary | None)
        self._history: list[tuple[str, str | None]] = []
        self._loop_count = 0
        self._llm_review_fn = llm_review_fn  # None → 降级 LCS

    async def record_and_check(
        self,
        action_signature: str,
        *,
        error_summary: str | None = None,
    ) -> bool:
        """记录行为签名并检测是否陷入循环。

        混合判断: LCS 周期重复(结构) → True; 窗口内有错误且 LLM 判同类错 → True;
        LLM 失败/未注入 → 回退 LCS 结果。

        Args:
            action_signature: 行为签名，如 "read_file:/src/main.py"
            error_summary: 本次调用的错误摘要 (错误工具的错误内容), 无错误传 None

        Returns:
            True if a loop pattern is detected.
        """
        self._history.append((action_signature, error_summary))

        # 🟡 结构预筛: LCS 周期重复 → True (零 LLM)
        if len(self._history) >= self._window_size:
            recent_sigs = [sig for sig, _ in self._history[-self._window_size :]]
            for period in [2, 3]:
                if self._is_periodic(recent_sigs, period):
                    self._loop_count += 1
                    logger.warning(
                        "Error loop detected (period=%d, count=%d): %s",
                        period,
                        self._loop_count,
                        " → ".join(recent_sigs[-period:]),
                    )
                    return True

        # 🟢 LLM 语义确认: 窗口满 + 有错误 + LCS 判否 → 判"换工具犯同类错"
        if (
            self._llm_review_fn is not None
            and len(self._history) >= self._window_size
            and self._has_recent_errors()
        ):
            judgement = await self._judge_semantic_loop()
            if (
                judgement is not None
                and judgement.is_same_error_loop
                and judgement.confidence >= 0.6
            ):
                self._loop_count += 1
                logger.warning(
                    "Error loop (semantic) detected (count=%d): %s",
                    self._loop_count,
                    judgement.reason,
                )
                return True

        return False

    def reset(self) -> None:
        """清除历史。"""
        self._history.clear()
        self._loop_count = 0

    @property
    def loop_count(self) -> int:
        """累计检测到的循环次数。"""
        return self._loop_count

    def get_break_prompt(self) -> str:
        """生成打破循环的 prompt 注入。"""
        if self._loop_count <= 1:
            return (
                "[注意] 检测到你在重复相同的操作。"
                "请换一种方法或工具来解决这个问题。"
            )
        return (
            "[紧急] 你已经多次陷入相同的循环。请立即停止当前方法，"
            "列出你尝试过的所有方法及其失败原因，然后提出一个完全不同的解决方案。"
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _has_recent_errors(self) -> bool:
        """窗口内是否有足够错误触发 LLM 语义判断 (控成本)。"""
        recent = self._history[-self._window_size :]
        errors = sum(1 for _, err in recent if err)
        return errors >= 2

    async def _judge_semantic_loop(self) -> ErrorLoopJudgement | None:
        """调 LLM 判断最近调用是否换工具犯同类错。失败返回 None (降级)。"""
        recent = self._history[-self._window_size :]
        actions_desc = "\n".join(
            f"- {sig}" + (f" (错误: {err[:100]})" if err else "")
            for sig, err in recent
        )
        prompt = ERROR_LOOP_JUDGEMENT_PROMPT.format(recent_actions=actions_desc)
        try:
            data = await self._llm_review_fn(prompt)
        except Exception as exc:
            logger.warning("error loop LLM judge failed, degrade to LCS: %s", exc)
            return None
        return ErrorLoopJudgement.from_llm(data if isinstance(data, dict) else {})

    def _is_periodic(self, actions: list[str], period: int) -> bool:
        """检测动作序列是否存在周期性重复。"""
        if len(actions) < period * 2:
            return False

        for i in range(len(actions) - period):
            if self._similarity(actions[i], actions[i + period]) < self._threshold:
                return False
        return True

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """字符串相似度（基于最长公共子序列比率）。"""
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0

        # LCS 动态规划
        m, n = len(a), len(b)
        if m > 200 or n > 200:
            # 超长字符串用简化方法
            common = set(a) & set(b)
            return len(common) / max(len(set(a)), len(set(b)), 1)

        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        lcs_len = dp[m][n]
        return (2 * lcs_len) / (m + n)
