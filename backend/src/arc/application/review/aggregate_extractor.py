"""从交付物中提取聚合引用。

扫描 todo 关联的 artifacts（特别是 tech_architecture 和 dev_report），
提取其中引用的聚合名称，建立 Todo ↔ 聚合的依赖关系。
"""

from __future__ import annotations

import re


def extract_aggregate_references(artifacts: list[dict]) -> set[str]:
    """从交付物内容中提取引用的聚合名称。

    支持以下识别模式:
    1. tech_architecture.data_model.entities[].name
    2. dev_report.implementation 中提到的实体名
    3. 任何交付物 content 中 "聚合"/"实体"/"aggregate" 关键词附近的名称

    Args:
        artifacts: Artifact 实体的 content dict 列表

    Returns:
        聚合名称集合
    """
    names: set[str] = set()

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue

        content = artifact.get("content", artifact)

        # 模式 1: data_model.entities
        data_model = content.get("data_model")
        if isinstance(data_model, dict):
            entities = data_model.get("entities", [])
            if isinstance(entities, list):
                for entity in entities:
                    if isinstance(entity, dict) and entity.get("name"):
                        names.add(entity["name"])

        # 模式 2: domain_design.bounded_contexts 中的聚合
        domain_design = content.get("domain_design")
        if isinstance(domain_design, dict):
            contexts = domain_design.get("bounded_contexts", [])
            if isinstance(contexts, list):
                for ctx in contexts:
                    if isinstance(ctx, dict):
                        for agg in ctx.get("aggregates", []):
                            if isinstance(agg, str):
                                names.add(agg)
                            elif isinstance(agg, dict) and agg.get("name"):
                                names.add(agg["name"])

        # 模式 3: event_storming.events 中的 aggregate 字段
        event_storming = content.get("event_storming")
        if isinstance(event_storming, dict):
            for event in event_storming.get("events", []):
                if isinstance(event, dict) and event.get("aggregate"):
                    names.add(event["aggregate"])
            for cmd in event_storming.get("commands", []):
                if isinstance(cmd, dict) and cmd.get("target_aggregate"):
                    names.add(cmd["target_aggregate"])

        # 模式 4: implementation 中提到的实体名 (从已知聚合列表匹配)
        impl = content.get("implementation")
        if isinstance(impl, dict):
            impl_text = str(impl)
            # 提取 PascalCase 标识符作为候选
            candidates = re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", impl_text)
            names.update(candidates)

    return names
