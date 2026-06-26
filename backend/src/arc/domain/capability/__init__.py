"""能力注册表聚合 (v6.8.0)。

agent/skill 能力声明管理: 可声明 (CRUD) + 可启用/禁用 + 按环节配置引用。
domain 层定义值对象与仓储契约; infrastructure (W1.2) 持久化; application (W1.3) 编排。
"""
from arc.domain.capability.errors import CapabilityError
from arc.domain.capability.repository import AbstractCapabilityRepository
from arc.domain.capability.value_objects import (
    CAPABILITY_TYPE_LABELS,
    Capability,
    CapabilityScope,
    CapabilityStatus,
    CapabilityType,
)

__all__ = [
    "CAPABILITY_TYPE_LABELS",
    "AbstractCapabilityRepository",
    "Capability",
    "CapabilityError",
    "CapabilityScope",
    "CapabilityStatus",
    "CapabilityType",
]
