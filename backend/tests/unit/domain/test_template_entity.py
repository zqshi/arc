"""Tests for DomainTemplate entity (v5.7.0 T1)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from arc.domain.errors import DomainError
from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import (
    TemplateCategory,
    TemplateScope,
    TemplateStatus,
)


def _make_template(
    *,
    status: TemplateStatus = TemplateStatus.DRAFT,
    usage_count: int = 0,
    success_count: int = 0,
    confidence: float = 0.8,
    last_used_at: datetime | None = None,
) -> DomainTemplate:
    return DomainTemplate(
        title="CRUD 模板",
        description="用户-内容-分类",
        category=TemplateCategory.CRUD_APP,
        source_user_id=uuid.uuid4(),
        status=status,
        usage_count=usage_count,
        success_count=success_count,
        confidence=confidence,
        last_used_at=last_used_at,
    )


class TestTemplateCreation:
    def test_minimal_creation(self):
        t = _make_template()
        assert t.status == TemplateStatus.DRAFT
        assert t.scope == TemplateScope.PERSONAL  # 默认个人
        assert t.confidence == 0.8
        assert t.usage_count == 0
        assert t.id is not None

    def test_defaults(self):
        t = _make_template()
        assert t.created_at is not None
        assert t.last_used_at is None
        assert t.embedding is None
        assert t.entity_patterns == []
        assert t.tags == []


class TestLifecycle:
    def test_confirm_draft(self):
        t = _make_template(status=TemplateStatus.DRAFT)
        t.confirm()
        assert t.status == TemplateStatus.CONFIRMED

    def test_confirm_non_draft_raises(self):
        """仅 draft 可 confirm (published/deprecated 不可再 confirm)。"""
        t = _make_template(status=TemplateStatus.PUBLISHED)
        with pytest.raises(DomainError, match="不允许"):
            t.confirm()

    def test_publish_confirmed(self):
        t = _make_template(status=TemplateStatus.CONFIRMED)
        t.publish()
        assert t.status == TemplateStatus.PUBLISHED

    def test_publish_draft_raises(self):
        """draft 未确认不可直接 publish (需先 confirm)。"""
        t = _make_template(status=TemplateStatus.DRAFT)
        with pytest.raises(DomainError, match="确认"):
            t.publish()

    def test_deprecate_published(self):
        t = _make_template(status=TemplateStatus.PUBLISHED)
        t.deprecate()
        assert t.status == TemplateStatus.DEPRECATED

    def test_deprecate_draft_raises(self):
        """draft 直接 deprecate 无意义 (未发布过)。"""
        t = _make_template(status=TemplateStatus.DRAFT)
        with pytest.raises(DomainError):
            t.deprecate()

    def test_deprecated_is_terminal(self):
        t = _make_template(status=TemplateStatus.DEPRECATED)
        with pytest.raises(DomainError):
            t.confirm()
        with pytest.raises(DomainError):
            t.publish()


class TestRecordUsage:
    def test_record_success_increments(self):
        t = _make_template(usage_count=0, success_count=0)
        t.record_usage(success=True)
        assert t.usage_count == 1
        assert t.success_count == 1
        assert t.last_used_at is not None

    def test_record_failure_increments_usage_only(self):
        t = _make_template()
        t.record_usage(success=False)
        assert t.usage_count == 1
        assert t.success_count == 0

    def test_success_rate(self):
        t = _make_template(usage_count=4, success_count=3)
        assert t.success_rate == 0.75

    def test_success_rate_zero_usage(self):
        t = _make_template(usage_count=0)
        assert t.success_rate == 0.0

    def test_record_usage_deprecated_raises(self):
        """已废弃模板不可再记录使用。"""
        t = _make_template(status=TemplateStatus.DEPRECATED)
        with pytest.raises(DomainError, match="废弃"):
            t.record_usage(success=True)


class TestDecayedConfidence:
    def test_recent_use_no_decay(self):
        """刚使用过, 无衰减。"""
        now = datetime.now(UTC)
        t = _make_template(confidence=0.8, last_used_at=now)
        assert t.compute_decayed_confidence() == 0.8

    def test_old_template_decays(self):
        """半年未用, confidence 衰减。"""
        old = datetime.now(UTC) - timedelta(days=180)
        t = _make_template(confidence=0.8, last_used_at=old)
        decayed = t.compute_decayed_confidence()
        assert decayed < 0.8
        # 半衰期 180 天, 应约为 0.4
        assert 0.35 <= decayed <= 0.45

    def test_never_used_decays_from_created(self):
        """从未使用, 从创建时间衰减。"""
        old_created = datetime.now(UTC) - timedelta(days=360)
        t = _make_template(confidence=0.8, last_used_at=None)
        # 手动设 created_at 模拟旧模板
        t.created_at = old_created
        decayed = t.compute_decayed_confidence()
        assert decayed <= 0.2  # 360 天约两个半衰期 (0.8 * 0.5^2 = 0.2)


class TestIsStale:
    def test_low_confidence_is_stale(self):
        t = _make_template(confidence=0.1)
        assert t.is_stale is True

    def test_high_confidence_not_stale(self):
        t = _make_template(confidence=0.8)
        assert t.is_stale is False
