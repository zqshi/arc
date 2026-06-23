"""BaasInstance 实体 — 追踪项目与 Supabase 实例的绑定关系 (v5.6.0 T1)。

状态机：provisioning → active ⇄ suspended → deleted
- apply_model 只能在 active 态执行，且 model_version 单调递增 (防增量 DDL 回退丢数据)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.baas.value_objects import (
    VALID_BAAS_TRANSITIONS,
    BaasStatus,
)
from arc.domain.errors import DomainError


@dataclass
class BaasInstance:
    """一个项目对应的 Supabase schema 实例。"""

    project_id: uuid.UUID
    schema_name: str
    supabase_url: str  # PostgREST endpoint
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    status: BaasStatus = BaasStatus.PROVISIONING
    last_applied_model_version: int = 0  # 对应 DomainModelSnapshot.version
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    activated_at: datetime | None = None

    # --- 状态转换行为 ---

    def _transition_to(self, target: BaasStatus) -> None:
        allowed = VALID_BAAS_TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise DomainError(
                f"当前状态 {self.status.value} 不允许转换到 {target.value}"
            )
        self.status = target

    def activate(self) -> None:
        """provisioning/suspended → active。schema 就绪或从暂停恢复。"""
        self._transition_to(BaasStatus.ACTIVE)
        self.activated_at = datetime.now(UTC)

    def apply_model(self, version: int) -> None:
        """应用 DomainModelSnapshot 版本到 Supabase schema。

        - 仅 active 态可执行 (provisioning 时 schema 未就绪)
        - version 必须单调递增 (≥当前)，相同版本是幂等 noop，回退抛错
          (增量 DDL 不可逆，回退会丢数据)
        """
        if self.status != BaasStatus.ACTIVE:
            raise DomainError(
                f"仅 active 状态可 apply model，当前: {self.status.value}"
            )
        if version < self.last_applied_model_version:
            raise DomainError(
                f"model_version 不能回退: 当前 {self.last_applied_model_version}，"
                f"尝试应用 {version}"
            )
        # 相同版本 = 幂等 noop (不抛错，不更新时间)
        if version > self.last_applied_model_version:
            self.last_applied_model_version = version

    def suspend(self) -> None:
        """active → suspended。暂停资源/计费，schema 保留。"""
        self._transition_to(BaasStatus.SUSPENDED)

    def delete(self) -> None:
        """active/suspended → deleted。软删除，终态不可恢复。"""
        self._transition_to(BaasStatus.DELETED)
