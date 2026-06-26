"""Artifact 字段可编辑性策略 (v5.5.0)。

区分用户可编辑 vs Agent 写入的字段:
- 文档类 artifact (DEV_REPORT/TEST_REPORT/...): 用户可整体编辑
- 工程产物 (APP_CODE/PROTOTYPE): Agent 写入，UI 只读
- 结构化 artifact (SERVICE_SPEC): 结构只读，仅特定字段 (notes) 可改

判断入口: `is_field_editable(artifact_type, field)` / `filter_editable_fields(...)`
"""
from __future__ import annotations

from collections.abc import Iterable

from arc.domain.artifact.value_objects import ArtifactType

_ALL_MARKER = "__all__"

EDITABLE_FIELDS: dict[ArtifactType, frozenset[str]] = {
    # 文档类 — 用户可自由编辑
    ArtifactType.REQUIREMENT_SPEC: frozenset({_ALL_MARKER}),
    ArtifactType.INTERACTION_DESIGN: frozenset({_ALL_MARKER}),
    ArtifactType.UI_SPEC: frozenset({_ALL_MARKER}),
    ArtifactType.TECH_ARCHITECTURE: frozenset({_ALL_MARKER}),
    ArtifactType.DEV_REPORT: frozenset({_ALL_MARKER}),
    ArtifactType.TEST_REPORT: frozenset({_ALL_MARKER}),
    ArtifactType.DEPLOY_REPORT: frozenset({_ALL_MARKER}),
    ArtifactType.EXPERIENCE_CARD: frozenset({_ALL_MARKER}),
    # 工程产物 — Agent 写入，UI 只读
    ArtifactType.PROTOTYPE: frozenset(),
    ArtifactType.APP_CODE: frozenset(),
    ArtifactType.BUILD: frozenset(),
    # 结构只读，备注可改
    ArtifactType.SERVICE_SPEC: frozenset({"notes"}),
    # Legacy
    ArtifactType.UI_DESIGN: frozenset(),
}


def is_field_editable(artifact_type: ArtifactType, field: str) -> bool:
    """判定单个字段是否可由用户编辑。"""
    editable = EDITABLE_FIELDS.get(artifact_type, frozenset())
    return _ALL_MARKER in editable or field in editable


def filter_editable_fields(
    artifact_type: ArtifactType, fields: Iterable[str]
) -> tuple[list[str], list[str]]:
    """将提交字段分组: (可编辑字段保持原序, 不可编辑字段按提交序)。

    Returns:
        (accepted, rejected) — accepted 保留输入顺序便于 UI 回显
    """
    editable = EDITABLE_FIELDS.get(artifact_type, frozenset())
    if _ALL_MARKER in editable:
        return list(fields), []
    accepted: list[str] = []
    rejected: list[str] = []
    for f in fields:
        if f in editable:
            accepted.append(f)
        else:
            rejected.append(f)
    return accepted, rejected
