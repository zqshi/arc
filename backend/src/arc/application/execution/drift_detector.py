"""目标漂移检测 — Harness §2.3.

在长对话/工具循环中检测 LLM 是否偏离原始目标。
使用关键词重叠度和行为模式重复检测。

分级响应:
- NONE: 正常继续
- MILD: 注入 reminder
- MODERATE: 插入重新聚焦 prompt
- SEVERE: 触发压缩 + 重新规划
"""

from __future__ import annotations

import logging
import re
from enum import IntEnum

logger = logging.getLogger(__name__)

# 中文停用词（高频无意义词）
_STOPWORDS = frozenset(
    "的了是在不有我他她它这那个们你我们他们可以"
    "就也都还要会到说一上下着过于和与被对于把从"
    "但如果因为所以虽然因此而且或者"
)


class DriftLevel(IntEnum):
    """漂移严重程度。"""

    NONE = 0
    MILD = 1
    MODERATE = 2
    SEVERE = 3


class DriftDetector:
    """目标漂移检测器。"""

    def __init__(
        self,
        original_goal: str,
        similarity_window: int = 5,
    ):
        self._original_goal = original_goal
        self._goal_keywords = _extract_keywords(original_goal)
        self._action_history: list[str] = []
        self._similarity_window = similarity_window

    def check_drift(self, current_action: str) -> DriftLevel:
        """记录行为并检测漂移程度。

        Args:
            current_action: 当前动作的文本描述（工具调用摘要或 LLM 输出片段）

        Returns:
            DriftLevel 枚举值
        """
        self._action_history.append(current_action)

        # 检测重复模式 → SEVERE
        if self._detect_loop():
            logger.warning("Drift: repetition loop detected")
            return DriftLevel.SEVERE

        # 计算与原始目标的相关度
        relevance = self._compute_relevance(current_action)

        if relevance < 0.15:
            logger.warning(
                "Drift SEVERE: relevance=%.2f for goal='%s'",
                relevance, self._original_goal[:50],
            )
            return DriftLevel.SEVERE
        if relevance < 0.30:
            logger.info("Drift MODERATE: relevance=%.2f", relevance)
            return DriftLevel.MODERATE
        if relevance < 0.50:
            return DriftLevel.MILD
        return DriftLevel.NONE

    def get_refocus_prompt(self, level: DriftLevel) -> str:
        """根据漂移程度生成重新聚焦的 prompt 注入。"""
        goal_reminder = f"原始目标: {self._original_goal}"

        if level == DriftLevel.MILD:
            return f"[提醒] {goal_reminder}。请确保你的下一步操作与此目标相关。"
        if level == DriftLevel.MODERATE:
            return (
                f"[重新聚焦] 你似乎偏离了目标。{goal_reminder}\n"
                "请停止当前操作，重新评估下一步应该做什么。"
            )
        if level == DriftLevel.SEVERE:
            return (
                f"[紧急重新规划] 检测到严重偏离或重复循环。{goal_reminder}\n"
                "请立即停止，列出已完成的工作和剩余任务，重新规划执行路径。"
            )
        return ""

    def reset(self) -> None:
        """清除行为历史。"""
        self._action_history.clear()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _compute_relevance(self, action: str) -> float:
        """计算当前行为与目标的关键词重叠度。"""
        if not self._goal_keywords:
            return 0.5  # 无目标关键词时默认中性

        action_keywords = _extract_keywords(action)
        if not action_keywords:
            return 0.3

        intersection = self._goal_keywords & action_keywords
        union = self._goal_keywords | action_keywords

        if not union:
            return 0.5

        # Jaccard similarity
        return len(intersection) / len(union)

    def _detect_loop(self) -> bool:
        """检测最近 N 步是否形成重复模式。"""
        history = self._action_history
        if len(history) < self._similarity_window:
            return False

        recent = history[-self._similarity_window:]

        # 检查周期 2 和 3
        for period in [2, 3]:
            if len(recent) < period * 2:
                continue
            is_periodic = True
            for i in range(len(recent) - period):
                if _string_similarity(recent[i], recent[i + period]) < 0.8:
                    is_periodic = False
                    break
            if is_periodic:
                return True

        return False


# ------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------


def _extract_keywords(text: str) -> set[str]:
    """从文本中提取有意义的关键词。"""
    # 中英文分词：按非字母数字字符分割
    tokens = re.findall(r"[\w一-鿿]+", text.lower())
    # 过滤停用词和短词
    return {
        t for t in tokens
        if len(t) > 1 and t not in _STOPWORDS and not t.isdigit()
    }


def _string_similarity(a: str, b: str) -> float:
    """简单字符串相似度（LCS ratio）。"""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # 使用简化的编辑距离近似
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if len(longer) == 0:
        return 1.0

    # 公共子串比率
    common = sum(1 for c in shorter if c in longer)
    return common / len(longer)
