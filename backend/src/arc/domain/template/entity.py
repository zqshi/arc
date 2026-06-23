"""DomainTemplate 实体 — 可复用领域模型模板 (v5.7.0 T1)。

从已交付项目的 BaasSchema 泛化提取, 新项目可一键套用。
类比 Experience (经验), 但模板是"可执行骨架"(强绑定), 经验是"参考信息"(弱绑定)。

衰减机制同 Experience: confidence 按半衰期 180 天递减, 长期不用变 stale。
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.errors import DomainError
from arc.domain.template.value_objects import (
    VALID_TEMPLATE_TRANSITIONS,
    TemplateCategory,
    TemplateScope,
    TemplateStatus,
)

STALE_THRESHOLD = 0.3
HALF_LIFE_DAYS = 180


@dataclass
class DomainTemplate:
    """一个可复用的领域模型模板。"""

    title: str
    description: str
    category: TemplateCategory
    source_user_id: uuid.UUID

    id: uuid.UUID = field(default_factory=uuid.uuid4)

    # 来源追溯
    source_project_id: uuid.UUID | None = None
    source_version_id: uuid.UUID | None = None

    # 核心内容: 泛化后的 BaasSchema (字段名是占位符)
    schema_template: dict = field(default_factory=dict)
    entity_patterns: list[str] = field(default_factory=list)  # ["User-Content-Category"]
    state_machine_patterns: list[str] = field(default_factory=list)  # ["draft→review→published"]
    permission_patterns: list[str] = field(default_factory=list)  # ["owner-based"]

    # 搜索
    tags: list[str] = field(default_factory=list)
    embedding: list[float] | None = None

    # 生命周期
    status: TemplateStatus = TemplateStatus.DRAFT
    scope: TemplateScope = TemplateScope.PERSONAL

    # 统计
    usage_count: int = 0
    success_count: int = 0  # 套用后成功部署数

    # 衰减
    confidence: float = 0.8
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used_at: datetime | None = None

    # --- 状态转换行为 ---

    def _transition_to(self, target: TemplateStatus) -> None:
        allowed = VALID_TEMPLATE_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise DomainError(
                f"当前状态 {self.status.value} 不允许转换到 {target.value}"
            )
        self.status = target

    def confirm(self) -> None:
        """draft → confirmed (人工审核确认可用)。"""
        self._transition_to(TemplateStatus.CONFIRMED)

    def publish(self) -> None:
        """confirmed → published。

        draft 不可直接 publish (需先 confirm 确保人工审核)。
        """
        if self.status == TemplateStatus.DRAFT:
            raise DomainError("draft 模板需先 confirm 确认后才能 publish")
        self._transition_to(TemplateStatus.PUBLISHED)

    def deprecate(self) -> None:
        """任意非 draft 状态 → deprecated (废弃, 终态)。"""
        if self.status == TemplateStatus.DRAFT:
            raise DomainError("draft 模板未发布, 无需 deprecate")
        self._transition_to(TemplateStatus.DEPRECATED)

    # --- 使用统计 ---

    def record_usage(self, *, success: bool) -> None:
        """记录一次套用结果, 更新统计 + last_used_at + confidence。"""
        if self.status == TemplateStatus.DEPRECATED:
            raise DomainError("已废弃模板不可再记录使用")
        self.usage_count += 1
        if success:
            self.success_count += 1
            self.confidence = min(1.0, round(self.confidence + 0.05, 3))
        else:
            self.confidence = max(0.0, round(self.confidence - 0.1, 3))
        self.last_used_at = datetime.now(UTC)

    @property
    def success_rate(self) -> float:
        """套用成功率 (成功部署 / 总套用次数)。"""
        if self.usage_count == 0:
            return 0.0
        return round(self.success_count / self.usage_count, 4)

    # --- 衰减 ---

    @property
    def is_stale(self) -> bool:
        """confidence 低于阈值视为陈旧。"""
        return self.compute_decayed_confidence() < STALE_THRESHOLD

    def compute_decayed_confidence(self) -> float:
        """按半衰期衰减后的 confidence (长期不用下降)。"""
        if self.confidence <= 0:
            return 0.0
        anchor = self.last_used_at or self.created_at
        days_elapsed = (datetime.now(UTC) - anchor).days
        if days_elapsed <= 0:
            return self.confidence
        decay = math.pow(0.5, days_elapsed / HALF_LIFE_DAYS)
        return round(self.confidence * decay, 4)
