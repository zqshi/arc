"""Unit tests for MemoryScorer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from arc.application.experience.scorer import MemoryScorer, _cosine_similarity


def _make_experience(**kwargs):
    """Create a mock Experience with specified attributes."""
    exp = MagicMock()
    exp.embedding = kwargs.get("embedding", [0.1, 0.2, 0.3])
    exp.last_reused_at = kwargs.get("last_reused_at", None)
    exp.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    exp.reuse_count = kwargs.get("reuse_count", 0)
    exp.source = MagicMock(value=kwargs.get("source", "todo_completion"))
    exp.status = MagicMock(value=kwargs.get("status", "draft"))
    return exp


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 0.001

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(_cosine_similarity(a, b)) < 0.001

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        # Clamped to 0.0
        assert _cosine_similarity(a, b) == 0.0

    def test_empty_vectors(self) -> None:
        assert _cosine_similarity([], []) == 0.0

    def test_mismatched_length(self) -> None:
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_zero_vector(self) -> None:
        assert _cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0


class TestMemoryScorerDimensions:
    def test_relevance_with_embedding(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(embedding=[1.0, 0.0, 0.0])
        query = [1.0, 0.0, 0.0]
        rel = scorer._relevance(exp, query)
        assert abs(rel - 1.0) < 0.01

    def test_relevance_no_embedding(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(embedding=None)
        rel = scorer._relevance(exp, [1.0, 0.0])
        assert rel == 0.5  # default neutral

    def test_relevance_no_query(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(embedding=[1.0, 0.0])
        rel = scorer._relevance(exp, None)
        assert rel == 0.5

    def test_recency_recent(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(
            last_reused_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        rec = scorer._recency(exp)
        assert rec > 0.99  # Very recent → close to 1.0

    def test_recency_old(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(
            last_reused_at=datetime.now(timezone.utc) - timedelta(days=90)
        )
        rec = scorer._recency(exp)
        assert rec < 0.8  # 90 days → exp(-0.3) ≈ 0.74, decayed from 1.0

    def test_frequency_zero(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(reuse_count=0)
        assert scorer._frequency(exp) == 0.0

    def test_frequency_saturates(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(reuse_count=15)
        assert scorer._frequency(exp) == 1.0  # capped at 10

    def test_authority_manual(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(source="manual")
        assert scorer._authority(exp) == 1.0

    def test_authority_todo_completion(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(source="todo_completion")
        assert scorer._authority(exp) == 0.6

    def test_user_explicit_confirmed(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(status="confirmed")
        assert scorer._user_explicit(exp) == 1.0

    def test_user_explicit_draft(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience(status="draft")
        assert scorer._user_explicit(exp) == 0.0


class TestMemoryScorerBatch:
    def test_batch_sorts_descending(self) -> None:
        scorer = MemoryScorer()
        exp_high = _make_experience(reuse_count=10, source="manual", status="confirmed")
        exp_low = _make_experience(reuse_count=0, source="todo_completion", status="draft")

        results = scorer.score_batch([exp_low, exp_high])
        assert results[0][0] is exp_high
        assert results[0][1] > results[1][1]

    def test_score_range(self) -> None:
        scorer = MemoryScorer()
        exp = _make_experience()
        score = scorer.score(exp)
        assert 0.0 <= score <= 1.0
