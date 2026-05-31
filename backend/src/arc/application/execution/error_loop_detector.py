"""Error Loop 检测 — Harness §5.4.

检测工具调用中的周期性重复模式（周期 2 或 3）。
用于识别 Agent 陷入 "相同错误 → 相同修复 → 相同错误" 的死循环。

使用滑动窗口 + 字符串相似度检测。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ErrorLoopDetector:
    """死循环检测器。

    记录工具调用的 action signature（如 "tool_name:input_hash"），
    在滑动窗口内检测周期为 2 或 3 的重复模式。
    """

    def __init__(
        self,
        window_size: int = 6,
        similarity_threshold: float = 0.85,
    ):
        self._window_size = window_size
        self._threshold = similarity_threshold
        self._history: list[str] = []
        self._loop_count = 0

    def record_and_check(self, action_signature: str) -> bool:
        """记录行为签名并检测是否陷入循环。

        Args:
            action_signature: 行为签名，如 "read_file:/src/main.py"
                              或 "run_command:npm test"

        Returns:
            True if a loop pattern is detected.
        """
        self._history.append(action_signature)

        if len(self._history) < self._window_size:
            return False

        recent = self._history[-self._window_size:]

        for period in [2, 3]:
            if self._is_periodic(recent, period):
                self._loop_count += 1
                logger.warning(
                    "Error loop detected (period=%d, count=%d): %s",
                    period, self._loop_count,
                    " → ".join(recent[-period:]),
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
