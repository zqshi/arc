"""DeliverableTracker 质量完成判定单元测试。"""

from __future__ import annotations

import uuid

from arc.domain.planning.entity import DeliverableTracker
from arc.domain.planning.value_objects import DeliverableStatus


class TestIsQualityComplete:
    def _tracker(self, deliverables: dict[str, DeliverableStatus]) -> DeliverableTracker:
        t = DeliverableTracker(todo_id=uuid.uuid4())
        t.deliverables = deliverables
        return t

    def test_all_qualified_and_produced_passes(self) -> None:
        t = self._tracker({
            "requirement_spec": DeliverableStatus.PRODUCED,
            "tech_architecture": DeliverableStatus.CONFIRMED,
        })
        assert t.is_quality_complete({"requirement_spec", "tech_architecture"}) is True

    def test_produced_but_not_qualified_fails(self) -> None:
        # 防虚假完成: PRODUCED 但没过门禁 (不在 qualified_types)
        t = self._tracker({"requirement_spec": DeliverableStatus.PRODUCED})
        assert t.is_quality_complete(set()) is False

    def test_in_progress_fails(self) -> None:
        t = self._tracker({"requirement_spec": DeliverableStatus.IN_PROGRESS})
        assert t.is_quality_complete({"requirement_spec"}) is False

    def test_empty_deliverables_fails(self) -> None:
        t = DeliverableTracker(todo_id=uuid.uuid4())
        assert t.is_quality_complete(set()) is False

    def test_partial_qualified_fails(self) -> None:
        # 两个 PRODUCED，但只有一个 qualified → 不通过
        t = self._tracker({
            "requirement_spec": DeliverableStatus.PRODUCED,
            "tech_architecture": DeliverableStatus.PRODUCED,
        })
        assert t.is_quality_complete({"requirement_spec"}) is False

    def test_is_complete_vs_is_quality_complete_divergence(self) -> None:
        # 同一 tracker: is_complete=True (都 PRODUCED) 但 is_quality_complete=False (未过门禁)
        t = self._tracker({"requirement_spec": DeliverableStatus.PRODUCED})
        assert t.is_complete is True
        assert t.is_quality_complete(set()) is False