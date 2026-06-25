"""TemplateApplyService — 模板适配 + apply 到新项目 Supabase (v5.7.0 T6)。

流程:
- adapt_template: 选中模板 + 新需求 → LLM 适配 → 具体项目 BaasSchema
  - LLM 把占位符 schema_template 转为具体表名/字段名的 BaasSchema
- apply_template: adapt → BaasService.provision + apply_model → 记录模板使用

LLM 适配失败抛 SchemaApplyError (无法生成有效 schema, 不 fallback 到空 schema)。
apply 失败也记录模板使用 (success=False, 用于 success_rate 统计)。
"""
from __future__ import annotations

import logging
import uuid

from arc.domain.baas.errors import SchemaApplyError
from arc.domain.baas.value_objects import (
    BaasSchema,
    ColumnDef,
    RlsPolicy,
    TableDef,
)
from arc.domain.template.entity import DomainTemplate

logger = logging.getLogger(__name__)


class TemplateApplyService:
    """模板适配 + apply 编排。"""

    def __init__(self, baas_service, template_repo) -> None:
        self._baas_service = baas_service
        self._template_repo = template_repo

    async def _adapt_with_llm(
        self, template: DomainTemplate, requirement: str, project_id: uuid.UUID
    ) -> dict:
        """LLM 适配: 模板 + 需求 → 具体 BaasSchema dict (可 override/mock)。

        输入: schema_template (占位符) + 新需求
        输出: 具体的 {tables, policies, transitions, actions} dict
        """
        from arc.application.ai.json_extract import extract_json
        from arc.application.ai.llm_adapter import LLMMessage
        from arc.application.ai.resilience import create_resilient_adapter

        prompt = (
            f"基于以下领域模型模板和新项目需求, 生成具体的项目 BaasSchema (JSON):\n"
            f"- 模板结构 (占位符, 需替换为具体表名/字段名): {template.schema_template}\n"
            f"- 模板模式: 实体={template.entity_patterns}, "
            f"状态机={template.state_machine_patterns}, "
            f"权限={template.permission_patterns}\n"
            f"- 新项目需求: {requirement}\n"
            f"输出: {{tables: [...], policies: [...], transitions: [...], actions: [...]}}"
        )
        adapter = create_resilient_adapter()
        try:
            resp = await adapter.chat(
                [LLMMessage(role="user", content=prompt)], temperature=0.3
            )
            data = extract_json(resp.content)
            if not isinstance(data, dict) or "tables" not in data:
                raise SchemaApplyError("LLM 输出无效: 缺少 tables 字段")
            return data
        finally:
            await adapter.close()

    @staticmethod
    def _dict_to_baas_schema(
        data: dict, project_id: uuid.UUID
    ) -> BaasSchema:
        """适配 dict → BaasSchema 值对象 (用 project_id 派生 schema_name)。"""
        schema_name = f"arc_{project_id.hex[:8]}"
        tables = [_dict_to_table(t) for t in data.get("tables", [])]
        policies = [_dict_to_policy(p) for p in data.get("policies", [])]
        # transitions/actions v5.7.0 暂不转 (留 v5.8.0 扩展)
        return BaasSchema(
            schema_name=schema_name,
            tables=tables,
            policies=policies,
            transitions=[],
            actions=[],
        )

    async def adapt_template(
        self, *, template: DomainTemplate, requirement: str, project_id: uuid.UUID
    ) -> BaasSchema:
        """模板 + 需求 → 适配后的 BaasSchema (不 apply)。"""
        try:
            data = await self._adapt_with_llm(template, requirement, project_id)
        except SchemaApplyError:
            raise
        except Exception as e:
            raise SchemaApplyError(f"模板适配失败: {e}") from e
        return self._dict_to_baas_schema(data, project_id)

    async def apply_template(
        self,
        *,
        template: DomainTemplate,
        requirement: str,
        project_id: uuid.UUID,
        supabase_url: str,
        model_version: int,
    ) -> None:
        """适配 + apply 到 Supabase + 记录模板使用。"""
        success = False
        try:
            schema = await self.adapt_template(
                template=template, requirement=requirement, project_id=project_id
            )
            await self._baas_service.provision(
                project_id=project_id,
                schema_name=schema.schema_name,
                supabase_url=supabase_url,
            )
            await self._baas_service.apply_model(
                project_id=project_id,
                schema=schema,
                model_version=model_version,
            )
            success = True
        finally:
            # 无论成功失败都记录模板使用 (用于 success_rate 统计)
            template.record_usage(success=success)
            try:
                await self._template_repo.update(template)
            except Exception:
                logger.warning(
                    "记录模板使用失败: template %s", template.id, exc_info=True
                )
            if not success:
                # 重新抛出原始异常 (适配/apply 失败)
                raise


# --- dict → 值对象转换 ---


def _dict_to_table(d: dict) -> TableDef:
    return TableDef(
        name=d["name"],
        columns=[_dict_to_column(c) for c in d.get("columns", [])],
        has_rls=d.get("has_rls", True),
        has_state_machine=d.get("has_state_machine", False),
        state_field=d.get("state_field"),
    )


def _dict_to_column(d: dict) -> ColumnDef:
    return ColumnDef(
        name=d["name"],
        type=d.get("type", "text"),
        nullable=d.get("nullable", True),
        default=d.get("default"),
        is_primary=d.get("is_primary", False),
        references=d.get("references"),
    )


def _dict_to_policy(d: dict) -> RlsPolicy:
    return RlsPolicy(
        table_name=d["table_name"],
        operation=d["operation"],
        role=d.get("role", "authenticated"),
        using_expr=d.get("using_expr"),
        check_expr=d.get("check_expr"),
    )
