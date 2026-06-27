"""Unit tests for Project entity scan lifecycle and soft-delete methods (v2.4.0)."""

from __future__ import annotations

from arc.domain.project.entity import Project
from arc.domain.project.value_objects import ProjectStatus


class TestProjectScanLifecycle:
    """Tests for scan_status state transitions."""

    def test_initial_scan_status_is_idle(self):
        p = Project(name="test")
        assert p.scan_status == "idle"
        assert p.scan_progress == ""
        assert p.scan_error == ""

    def test_start_scan(self):
        p = Project(name="test")
        p.start_scan()
        assert p.scan_status == "scanning"
        assert p.scan_progress == ""
        assert p.scan_error == ""

    def test_update_scan_progress(self):
        p = Project(name="test")
        p.start_scan()
        p.update_scan_progress("正在分析第1批...")
        assert p.scan_progress == "正在分析第1批..."
        assert p.scan_status == "scanning"

    def test_complete_scan(self):
        p = Project(name="test")
        p.start_scan()
        p.update_scan_progress("分析中")
        p.complete_scan("这是项目摘要", "fp123")
        assert p.scan_status == "completed"
        assert p.codebase_summary == "这是项目摘要"
        assert p.scan_fingerprint == "fp123"
        assert p.scan_progress == ""

    def test_fail_scan(self):
        p = Project(name="test")
        p.start_scan()
        p.fail_scan("LLM 调用超时")
        assert p.scan_status == "error"
        assert p.scan_error == "LLM 调用超时"
        assert p.scan_progress == ""

    def test_scan_restart_after_error(self):
        p = Project(name="test")
        p.fail_scan("first error")
        p.start_scan()
        assert p.scan_status == "scanning"
        assert p.scan_error == ""


class TestProjectSoftDelete:
    """Tests for logical delete and restore."""

    def test_soft_delete_sets_status_and_timestamp(self):
        p = Project(name="test")
        assert p.deleted_at is None
        assert p.is_deleted is False

        p.soft_delete()
        assert p.status == ProjectStatus.DELETED
        assert p.deleted_at is not None
        assert p.is_deleted is True

    def test_restore_clears_deleted_at(self):
        p = Project(name="test")
        p.soft_delete()
        p.restore()
        assert p.status == ProjectStatus.ACTIVE
        assert p.deleted_at is None
        assert p.is_deleted is False

    def test_is_deleted_property(self):
        p = Project(name="test")
        assert p.is_deleted is False
        p.soft_delete()
        assert p.is_deleted is True
        p.restore()
        assert p.is_deleted is False


class TestProjectScanTimestamps:
    """Verify updated_at is refreshed on state changes."""

    def test_start_scan_updates_timestamp(self):
        p = Project(name="test")
        old_ts = p.updated_at
        p.start_scan()
        assert p.updated_at >= old_ts

    def test_complete_scan_updates_timestamp(self):
        p = Project(name="test")
        p.start_scan()
        old_ts = p.updated_at
        p.complete_scan("summary", "fp")
        assert p.updated_at >= old_ts

    def test_soft_delete_updates_timestamp(self):
        p = Project(name="test")
        old_ts = p.updated_at
        p.soft_delete()
        assert p.updated_at >= old_ts
