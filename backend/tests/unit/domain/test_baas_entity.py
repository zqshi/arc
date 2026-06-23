"""Tests for domain/baas BaasInstance entity (v5.6.0 T1)."""

import uuid

import pytest

from arc.domain.baas.entity import BaasInstance
from arc.domain.baas.value_objects import BaasStatus
from arc.domain.errors import DomainError


def _make_instance(status: BaasStatus = BaasStatus.PROVISIONING) -> BaasInstance:
    return BaasInstance(
        project_id=uuid.uuid4(),
        schema_name="arc_proj123",
        supabase_url="http://localhost:54321",
        status=status,
    )


class TestBaasInstanceCreation:
    def test_minimal_creation(self):
        inst = _make_instance()
        assert inst.status == BaasStatus.PROVISIONING
        assert inst.last_applied_model_version == 0  # 未应用过模型
        assert inst.id is not None

    def test_defaults(self):
        inst = _make_instance()
        assert inst.created_at is not None
        assert inst.activated_at is None


class TestProvisionFlow:
    def test_provisioning_to_active(self):
        inst = _make_instance(BaasStatus.PROVISIONING)
        inst.activate()
        assert inst.status == BaasStatus.ACTIVE
        assert inst.activated_at is not None

    def test_activate_from_non_provisioning_raises(self):
        """deleted 是终态，不能 activate (provisioning/suspended 都可激活)。"""
        inst = _make_instance(BaasStatus.DELETED)
        with pytest.raises(DomainError, match="不允许转换到"):
            inst.activate()

    def test_apply_model_records_version(self):
        inst = _make_instance(BaasStatus.ACTIVE)
        inst.apply_model(3)
        assert inst.last_applied_model_version == 3
        inst.apply_model(4)
        assert inst.last_applied_model_version == 4

    def test_apply_model_only_when_active(self):
        """非 active 状态不允许 apply (provisioning 时 schema 未就绪)。"""
        inst = _make_instance(BaasStatus.PROVISIONING)
        with pytest.raises(DomainError, match="active 状态"):
            inst.apply_model(1)


class TestSuspendDelete:
    def test_suspend_active(self):
        inst = _make_instance(BaasStatus.ACTIVE)
        inst.suspend()
        assert inst.status == BaasStatus.SUSPENDED

    def test_suspend_provisioning_raises(self):
        inst = _make_instance(BaasStatus.PROVISIONING)
        with pytest.raises(DomainError):
            inst.suspend()

    def test_resume_from_suspended(self):
        inst = _make_instance(BaasStatus.SUSPENDED)
        inst.activate()
        assert inst.status == BaasStatus.ACTIVE

    def test_delete_active(self):
        inst = _make_instance(BaasStatus.ACTIVE)
        inst.delete()
        assert inst.status == BaasStatus.DELETED

    def test_delete_suspended(self):
        inst = _make_instance(BaasStatus.SUSPENDED)
        inst.delete()
        assert inst.status == BaasStatus.DELETED

    def test_deleted_is_terminal(self):
        inst = _make_instance(BaasStatus.DELETED)
        with pytest.raises(DomainError):
            inst.activate()
        with pytest.raises(DomainError):
            inst.suspend()


class TestApplyModelVersionGuard:
    def test_apply_lower_version_raises(self):
        """不允许回退 model_version (增量 DDL 不可逆，防数据丢失)。"""
        inst = _make_instance(BaasStatus.ACTIVE)
        inst.apply_model(5)
        with pytest.raises(DomainError, match="不能回退"):
            inst.apply_model(3)

    def test_apply_same_version_is_noop(self):
        inst = _make_instance(BaasStatus.ACTIVE)
        inst.apply_model(5)
        inst.apply_model(5)  # 不抛错
        assert inst.last_applied_model_version == 5
