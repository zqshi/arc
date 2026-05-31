"""五维加权检索打分 — Harness §6.3.

维度与权重:
- relevance (0.40): cosine similarity with query embedding
- recency (0.20): exponential decay from last_reused_at
- frequency (0.15): reuse_count normalized to [0, 1]
- authority (0.15): source weight (manual > version_release > todo_completion)
- user_explicit (0.10): confirmed by user = 1.0

用于替代 ExperienceService.search_similar() 中的纯 cosine 排序。
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc.domain.experience.entity import Experience

logger = logging.getLogger(__name__)


# Source authority weights
_SOURCE_WEIGHTS = {
    "manual": 1.0,
    "version_release": 0.8,
    "scope_change": 0.7,
    "todo_completion": 0.6,
}


class MemoryScorer:
    """五维加权检索打分器。"""

    WEIGHTS = {
        "relevance": 0.40,
        "recency": 0.20,
        "frequency": 0.15,
        "authority": 0.15,
        "user_explicit": 0.10,
    }

    def score(
        self,
        experience: Experience,
        query_embedding: list[float] | None = None,
    ) -> float:
        """计算单条经验的综合得分。"""
        scores = {
            "relevance": self._relevance(experience, query_embedding),
            "recency": self._recency(experience),
            "frequency": self._frequency(experience),
            "authority": self._authority(experience),
            "user_explicit": self._user_explicit(experience),
        }

        total = sum(self.WEIGHTS[k] * v for k, v in scores.items())
        return round(total, 4)

    def score_batch(
        self,
        experiences: list[Experience],
        query_embedding: list[float] | None = None,
    ) -> list[tuple[Experience, float]]:
        """批量打分并降序排列。"""
        scored = [
            (exp, self.score(exp, query_embedding))
            for exp in experiences
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    # ------------------------------------------------------------------
    # Dimension scorers
    # ------------------------------------------------------------------

    @staticmethod
    def _relevance(
        exp: Experience, query_embedding: list[float] | None,
    ) -> float:
        """Cosine similarity with query embedding."""
        if query_embedding is None or not exp.embedding:
            return 0.5  # 无向量时返回中性分

        return _cosine_similarity(query_embedding, exp.embedding)

    @staticmethod
    def _recency(exp: Experience) -> float:
        """Exponential decay from last access time.

        Half-life: ~30 days (decay rate 0.1/30 per day).
        """
        anchor = exp.last_reused_at or exp.created_at
        if not anchor:
            return 0.3

        now = datetime.now(timezone.utc)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)

        days_elapsed = max(0, (now - anchor).total_seconds() / 86400)
        return math.exp(-0.1 * days_elapsed / 30)

    @staticmethod
    def _frequency(exp: Experience) -> float:
        """Reuse count normalized to [0, 1], saturates at 10."""
        return min(exp.reuse_count / 10, 1.0)

    @staticmethod
    def _authority(exp: Experience) -> float:
        """Source-based authority weight."""
        source_value = exp.source.value if hasattr(exp.source, "value") else str(exp.source)
        return _SOURCE_WEIGHTS.get(source_value, 0.5)

    @staticmethod
    def _user_explicit(exp: Experience) -> float:
        """1.0 if user-confirmed, 0.0 otherwise."""
        status_value = exp.status.value if hasattr(exp.status, "value") else str(exp.status)
        return 1.0 if status_value == "confirmed" else 0.0


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if len(a) != len(b) or not a:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return max(0.0, min(1.0, dot / (norm_a * norm_b)))
