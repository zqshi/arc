"""TemplateExtractionService — 从 BaasSchema 泛化提取可复用模板 (v5.7.0 T4)。

职责:
- extract_structure (纯逻辑): 具体表名→占位符, 保留列类型/主键/外键结构
- detect_*_patterns: 识别实体/状态机/权限模式
- infer_category: 从 schema 特征推断分类
- extract_template (编排): 结构泛化 + LLM 生成标题/描述 → DomainTemplate (draft)

LLM 步骤封装为 _generate_title_desc, 失败时 fallback 到结构化标题 (不阻断)。
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from arc.domain.baas.value_objects import BaasSchema
from arc.domain.template.entity import DomainTemplate
from arc.domain.template.value_objects import TemplateCategory

logger = logging.getLogger(__name__)

# 占位符表名前缀 (泛化: orders → table_1, order_items → table_2)
_PLACEHOLDER_PREFIX = "table_"

# 电商特征词
_ECOMM_KEYWORDS = {"order", "payment", "cart", "product", "invoice", "amount", "price"}
# 社交特征词
_SOCIAL_KEYWORDS = {"follow", "like", "comment", "share", "feed", "friend"}
# 工作流特征词
_WORKFLOW_KEYWORDS = {"approval", "ticket", "task", "assign", "review", "approve"}
# SaaS 多租户特征
_SAAS_KEYWORDS = {"tenant", "organization", "workspace", "subscription", "plan"}


class TemplateExtractionService:
    """从已交付项目的 BaasSchema 提取可复用领域模型模板。"""

    # --- 纯结构泛化 (可测试, 无 IO) ---

    @staticmethod
    def extract_structure(schema: BaasSchema) -> dict:
        """具体 BaasSchema → 泛化 schema_template (占位符表名, 保留结构)。"""
        name_map = {}
        tables_out = []
        for idx, table in enumerate(schema.tables, start=1):
            placeholder = f"{_PLACEHOLDER_PREFIX}{idx}"
            name_map[table.name] = placeholder
            tables_out.append({
                "name": placeholder,
                "original_role": _infer_table_role(table.name),
                "columns": [_column_to_template(c) for c in table.columns],
                "has_rls": table.has_rls,
                "has_state_machine": table.has_state_machine,
                "state_field": table.state_field,
            })

        # 外键引用也泛化为占位符
        for t in tables_out:
            for c in t["columns"]:
                if c.get("references"):
                    ref_table = c["references"].split("(")[0]
                    if ref_table in name_map:
                        c["references"] = f"{name_map[ref_table]}(id)"

        return {"tables": tables_out, "name_map_count": len(name_map)}

    @staticmethod
    def detect_entity_patterns(schema: BaasSchema) -> list[str]:
        """识别实体关系模式 (主从/一对多)。"""
        patterns: list[str] = []
        # 有外键的表 → 主从关系
        has_master_detail = any(
            any(c.references for c in t.columns) for t in schema.tables
        )
        if has_master_detail:
            patterns.append("master-detail (主从关系)")

        # 有 user_id 的表 → owner-owned 模式
        has_user_owned = any(
            any(c.name == "user_id" for c in t.columns) for t in schema.tables
        )
        if has_user_owned:
            patterns.append("owner-resource (用户拥有资源)")

        return patterns or ["simple-crud (单实体)"]

    @staticmethod
    def detect_state_machine_patterns(schema: BaasSchema) -> list[str]:
        """识别状态机模式 (链式/分支)。"""
        if not schema.transitions:
            return []

        # 按 entity 分组跃迁
        by_entity: dict[str, list] = {}
        for t in schema.transitions:
            by_entity.setdefault(t.entity, []).append(t)

        patterns: list[str] = []
        for entity, transitions in by_entity.items():
            # 构建状态图, 判断链式 vs 分支
            out_degrees = {}
            for t in transitions:
                out_degrees[t.from_state] = out_degrees.get(t.from_state, 0) + 1
            max_branching = max(out_degrees.values()) if out_degrees else 1
            if max_branching <= 1:
                patterns.append(f"chain (链式状态机, {len(transitions)} 步)")
            else:
                patterns.append(f"branching (分支状态机, 最大分支 {max_branching})")
        return patterns

    @staticmethod
    def detect_permission_patterns(schema: BaasSchema) -> list[str]:
        """识别 RLS 权限模式。"""
        patterns: set[str] = set()
        for p in schema.policies:
            expr = (p.using_expr or "") + " " + (p.check_expr or "")
            if "auth.uid()" in expr and "user_id" in expr:
                patterns.add("owner-based (按拥有者隔离)")
            if p.role == "anon" and "true" in expr.lower():
                patterns.add("public-read (公开读)")
        return sorted(patterns)

    @staticmethod
    def infer_category(schema: BaasSchema) -> TemplateCategory:
        """从 schema 特征推断模板分类。"""
        all_text = " ".join(
            t.name for t in schema.tables
        ).lower()
        for c in _columns_text(schema):
            all_text += " " + c.lower()

        if _has_keywords(all_text, _ECOMM_KEYWORDS):
            return TemplateCategory.ECOMMERCE
        if _has_keywords(all_text, _SOCIAL_KEYWORDS):
            return TemplateCategory.SOCIAL
        if _has_keywords(all_text, _WORKFLOW_KEYWORDS):
            return TemplateCategory.WORKFLOW
        if _has_keywords(all_text, _SAAS_KEYWORDS):
            return TemplateCategory.SAAS_BACKEND
        if schema.tables:
            return TemplateCategory.CRUD_APP
        return TemplateCategory.CUSTOM

    # --- 编排: LLM 标题 + 结构泛化 → DomainTemplate ---

    async def _generate_title_desc(
        self, schema: BaasSchema, category: TemplateCategory
    ) -> tuple[str, str]:
        """LLM 生成模板标题/描述 (可被 mock/override)。"""
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.ai.resilience import create_resilient_adapter

        structure = self.extract_structure(schema)
        prompt = (
            f"为以下{category.value}类领域模型模板生成简短标题和描述 (JSON): "
            f"{{title, description}}。结构: {structure}"
        )
        adapter = create_resilient_adapter()
        try:
            resp = await adapter.chat(
                [LLMMessage(role="user", content=prompt)], temperature=0.3
            )
            from arc.application.ai.json_extract import extract_json
            data = extract_json(resp.content)
            if isinstance(data, dict):
                return data.get("title", ""), data.get("description", "")
        finally:
            await adapter.close()
        return "", ""

    async def extract_template(
        self,
        *,
        schema: BaasSchema,
        source_user_id: uuid.UUID,
        source_project_id: uuid.UUID | None = None,
        source_version_id: uuid.UUID | None = None,
    ) -> DomainTemplate:
        """从 BaasSchema 提取 DomainTemplate (draft, 待人工确认)。"""
        category = self.infer_category(schema)
        structure = self.extract_structure(schema)
        entity_patterns = self.detect_entity_patterns(schema)
        state_patterns = self.detect_state_machine_patterns(schema)
        perm_patterns = self.detect_permission_patterns(schema)

        # LLM 生成标题/描述 (失败 fallback)
        title, description = "", ""
        try:
            title, description = await self._generate_title_desc(schema, category)
        except Exception:
            logger.warning("LLM title generation failed, using fallback", exc_info=True)

        if not title:
            title = self._fallback_title(category, schema)
        if not description:
            description = self._fallback_description(
                entity_patterns, state_patterns, perm_patterns
            )

        # v5.8.0: 生成 embedding (标题+描述+模式), 供后续语义匹配
        embedding = await self._generate_embedding(
            title, description, entity_patterns, state_patterns, perm_patterns
        )

        return DomainTemplate(
            title=title,
            description=description,
            category=category,
            source_user_id=source_user_id,
            source_project_id=source_project_id,
            source_version_id=source_version_id,
            schema_template=structure,
            entity_patterns=entity_patterns,
            state_machine_patterns=state_patterns,
            permission_patterns=perm_patterns,
            tags=[category.value],
            embedding=embedding,
        )

    async def _generate_embedding(
        self,
        title: str,
        description: str,
        entity_patterns: list[str],
        state_patterns: list[str],
        perm_patterns: list[str],
    ) -> list[float] | None:
        """LLM 生成模板语义向量 (用于 search_matching 向量搜索)。

        embed 文本 = 标题 + 描述 + 各类模式 (让向量承载完整语义)。
        失败返回 None (匹配时该模板不参与向量搜索, 不阻断)。
        """
        from arc.application.ai.resilience import create_resilient_adapter

        embed_text = " ".join([
            title, description,
            *entity_patterns, *state_patterns, *perm_patterns,
        ]).strip()
        if not embed_text:
            return None
        try:
            adapter = create_resilient_adapter()
            try:
                return await adapter.embed(embed_text)
            finally:
                await adapter.close()
        except Exception:
            logger.warning("Template embedding generation failed", exc_info=True)
            return None

    @staticmethod
    def _fallback_title(category: TemplateCategory, schema: BaasSchema) -> str:
        category_labels = {
            TemplateCategory.ECOMMERCE: "电商",
            TemplateCategory.SOCIAL: "社交",
            TemplateCategory.WORKFLOW: "工作流",
            TemplateCategory.SAAS_BACKEND: "SaaS 后台",
            TemplateCategory.CRUD_APP: "CRUD 应用",
            TemplateCategory.CUSTOM: "自定义",
        }
        label = category_labels.get(category, "通用")
        return f"{label}模板 ({len(schema.tables)} 表)"

    @staticmethod
    def _fallback_description(
        entity_patterns: list[str],
        state_patterns: list[str],
        perm_patterns: list[str],
    ) -> str:
        parts = []
        if entity_patterns:
            parts.append(f"实体模式: {', '.join(entity_patterns)}")
        if state_patterns:
            parts.append(f"状态机: {', '.join(state_patterns)}")
        if perm_patterns:
            parts.append(f"权限: {', '.join(perm_patterns)}")
        return " | ".join(parts) if parts else "通用领域模型模板"


# --- 辅助函数 ---


def _column_to_template(col) -> dict:
    """ColumnDef → 模板列 dict (保留 type/主键/外键, 去具体语义)。"""
    out: dict[str, Any] = {
        "name": col.name,
        "type": col.type,
        "nullable": col.nullable,
        "is_primary": col.is_primary,
    }
    if col.references:
        out["references"] = col.references
    return out


def _infer_table_role(name: str) -> str:
    """从表名推断角色 (order→订单主表, *_items→明细)。"""
    lower = name.lower()
    if "order" in lower and "item" not in lower:
        return "order-main"
    if "item" in lower or "detail" in lower:
        return "line-item"
    if "user" in lower:
        return "user"
    if "comment" in lower or "review" in lower:
        return "comment"
    return "entity"


def _columns_text(schema: BaasSchema) -> list[str]:
    return [c.name for t in schema.tables for c in t.columns]


def _has_keywords(text: str, keywords: set[str]) -> bool:
    return any(kw in text for kw in keywords)
