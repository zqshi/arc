"""Project 领域模型快照机制单元测试。"""


import pytest

from arc.domain.project.entity import Project
from arc.domain.project.value_objects import ModelChangeTrigger


def _make_project(**overrides) -> Project:
    defaults = dict(name="Test Project")
    return Project(**{**defaults, **overrides})


def _make_domain_model(version: int = 1, **extra) -> dict:
    return {
        "version": version,
        "aggregates": [{"name": "Order", "fields": ["id", "total"]}],
        "subdomains": [],
        "contexts": [],
        "relations": [],
        **extra,
    }


class TestUpgradeDomainModel:
    def test_creates_snapshot(self):
        p = _make_project(domain_model=_make_domain_model(1))
        assert len(p.domain_model_history) == 0

        p.upgrade_domain_model(
            _make_domain_model(0),  # version 会被覆盖
            trigger=ModelChangeTrigger.EXTRACTOR,
            trigger_todo_id="todo-123",
        )

        assert len(p.domain_model_history) == 1
        snap = p.domain_model_history[0]
        assert snap["version"] == 1  # 旧版本号
        assert snap["trigger"] == "extractor"
        assert snap["trigger_todo_id"] == "todo-123"
        assert snap["content"]["aggregates"][0]["name"] == "Order"

    def test_increments_version(self):
        p = _make_project(domain_model=_make_domain_model(1))
        new_version = p.upgrade_domain_model(
            _make_domain_model(0),
            trigger=ModelChangeTrigger.MANUAL,
        )
        assert new_version == 2
        assert p.domain_model["version"] == 2

    def test_sets_updated_at(self):
        p = _make_project(domain_model=_make_domain_model(1))
        new_version = p.upgrade_domain_model(
            _make_domain_model(0),
            trigger=ModelChangeTrigger.UPGRADE,
        )
        assert p.domain_model.get("updated_at") is not None
        assert new_version == 2

    def test_snapshot_is_deep_copy(self):
        original_model = _make_domain_model(1)
        p = _make_project(domain_model=original_model)
        p.upgrade_domain_model(
            {"aggregates": [{"name": "Payment"}]},
            trigger=ModelChangeTrigger.EXTRACTOR,
        )

        # 修改当前 model 不影响快照
        p.domain_model["aggregates"].append({"name": "Shipping"})
        snap_content = p.domain_model_history[0]["content"]
        assert len(snap_content["aggregates"]) == 1
        assert snap_content["aggregates"][0]["name"] == "Order"

    def test_multiple_upgrades(self):
        p = _make_project(domain_model=_make_domain_model(1))

        p.upgrade_domain_model(
            _make_domain_model(0, aggregates=[{"name": "V2"}]),
            trigger=ModelChangeTrigger.EXTRACTOR,
        )
        p.upgrade_domain_model(
            _make_domain_model(0, aggregates=[{"name": "V3"}]),
            trigger=ModelChangeTrigger.MANUAL,
        )

        assert len(p.domain_model_history) == 2
        assert p.domain_model["version"] == 3
        assert p.domain_model_history[0]["version"] == 1
        assert p.domain_model_history[1]["version"] == 2

    def test_from_empty_model(self):
        p = _make_project()
        assert p.domain_model == {}

        new_version = p.upgrade_domain_model(
            _make_domain_model(0),
            trigger=ModelChangeTrigger.EXTRACTOR,
        )
        assert new_version == 1
        assert len(p.domain_model_history) == 1
        assert p.domain_model_history[0]["version"] == 0
        assert p.domain_model_history[0]["content"] == {}


class TestRollbackDomainModel:
    def test_rollback_to_previous_version(self):
        p = _make_project(domain_model=_make_domain_model(1))
        p.upgrade_domain_model(
            _make_domain_model(0, aggregates=[{"name": "V2"}]),
            trigger=ModelChangeTrigger.MANUAL,
        )
        assert p.domain_model["version"] == 2

        p.rollback_domain_model(to_version=1)

        # 回滚后内容恢复到 v1
        assert p.domain_model["aggregates"][0]["name"] == "Order"
        # 回滚本身产生快照
        assert len(p.domain_model_history) == 2
        assert p.domain_model_history[1]["trigger"] == "rollback"
        assert p.domain_model_history[1]["version"] == 2

    def test_rollback_creates_snapshot_of_current(self):
        p = _make_project(domain_model=_make_domain_model(1))
        p.upgrade_domain_model(
            _make_domain_model(0, aggregates=[{"name": "V2"}]),
            trigger=ModelChangeTrigger.MANUAL,
        )
        p.rollback_domain_model(to_version=1)

        # 被回滚的版本保存在快照中
        rollback_snap = p.domain_model_history[-1]
        assert rollback_snap["content"]["aggregates"][0]["name"] == "V2"

    def test_rollback_nonexistent_version_raises(self):
        p = _make_project(domain_model=_make_domain_model(1))
        with pytest.raises(ValueError, match="Version 99 not found"):
            p.rollback_domain_model(to_version=99)

    def test_rollback_is_deep_copy(self):
        p = _make_project(domain_model=_make_domain_model(1))
        p.upgrade_domain_model(
            _make_domain_model(0, aggregates=[{"name": "V2"}]),
            trigger=ModelChangeTrigger.MANUAL,
        )
        p.rollback_domain_model(to_version=1)

        # 修改 rollback 后的 model 不影响快照
        p.domain_model["aggregates"].append({"name": "Added"})
        snap_content = p.domain_model_history[0]["content"]
        agg_names = [a["name"] for a in snap_content.get("aggregates", [])]
        assert "Added" not in agg_names


class TestDomainModelVersion:
    def test_version_from_empty(self):
        p = _make_project()
        assert p.domain_model_version == 0

    def test_version_after_upgrade(self):
        p = _make_project(domain_model=_make_domain_model(3))
        assert p.domain_model_version == 3

        p.upgrade_domain_model(
            _make_domain_model(0),
            trigger=ModelChangeTrigger.MANUAL,
        )
        assert p.domain_model_version == 4
