"""交付物逻辑依赖图 — 声明式 DAG，定义各交付物的逻辑前置。

用于"依赖前置软约束"：产出某交付物时，其逻辑前置产物必须已达标，防止空中楼阁。
这是"逻辑前置"(业务依赖) 而非"产出顺序"——free 模式仍可灵活产出，
但产出 tech_architecture 那一刻 requirement_spec 必须已达标。

纯数据 + 纯函数，无 infra 依赖 (保持 domain 零违规)。
"""

from __future__ import annotations

# 有向无环图: artifact_type 字符串值 → 其逻辑前置 (必须达标才能产出它)
# 用字符串值而非 ArtifactType 枚举，避免 domain 内跨模块循环 import。
#
# 依赖约束是三档(STRICT/MODERATE/FREE)共享的硬不变量: 依赖满足是产出下游的前提,
# 与模式无关。三档只在"遍历策略 + 校验严格度"上差异, 依赖守卫统一硬阻断 (见
# artifact_extractor.py)。此图即交付物顺序的唯一真相源。
#
# 修正记录 (v6.15): 补全 prototype→tech_architecture/app_code、app_code→dev_report/
# test_report 的依赖, 堵"没原型就写代码/没代码就报告/没代码就测试"的空中楼阁。
# build 不入此图 (类型裁剪产物, 仅 BINARY_APP 存在, 见 value_objects._BUILD_ONLY)。
DELIVERABLE_DEPENDENCIES: dict[str, list[str]] = {
    "requirement_spec": [],  # 根，无前置
    "interaction_design": ["requirement_spec"],
    "ui_spec": ["requirement_spec", "interaction_design"],
    "prototype": ["requirement_spec", "interaction_design", "ui_spec"],
    "tech_architecture": ["requirement_spec", "prototype"],
    "service_spec": ["tech_architecture"],
    "dev_report": ["tech_architecture", "service_spec", "app_code"],
    "app_code": ["tech_architecture", "service_spec", "prototype"],
    "test_report": ["requirement_spec", "tech_architecture", "app_code"],
    "deploy_report": ["dev_report", "app_code", "test_report"],
    "experience_card": ["requirement_spec", "dev_report"],
}


def missing_prerequisites(target: str, qualified_types: set[str]) -> list[str]:
    """返回 target 的逻辑前置中尚未达标的列表 (保持声明顺序)。

    Args:
        target: 目标交付物类型 (字符串值，对应 ArtifactType.value)
        qualified_types: 已达标 (门禁通过) 的交付物类型集合

    Returns:
        未达标的前置列表；target 无前置或前置全达标时返回空列表。
        未知 target 返回空列表 (不阻断，由质量门禁兜底)。
    """
    deps = DELIVERABLE_DEPENDENCIES.get(target, [])
    return [d for d in deps if d not in qualified_types]
