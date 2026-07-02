"""DomainModelApplier — DomainModelSnapshot → BaasSchema → apply (v5.6.0 T8)。

职责: 把 Arc 既有的领域模型快照 (aggregates/fields 结构) 转换为 BaasSchema,
然后调 BaasService.provision + apply_model 落地到 Supabase。

转换规则 (保守, 信任既有模型):
- 每个聚合 → 一张表, 表名 = 聚合名小写复数化
- 聚合字段 → 列; "id" 字段 → UUID 主键; 无 id 时自动补
- 默认启用 RLS (supabase 安全默认)
- 不生成 RLS 策略/状态机/Action (领域模型快照不含这些语义, 留给 Agent 后续补)

不直接执行 SQL, 而是产出 BaasSchema 交给 BaasService (单一编排入口)。
"""
from __future__ import annotations

import logging
import re
import uuid

from arc.domain.baas.value_objects import (
    BaasSchema,
    ColumnDef,
    RlsPolicy,
    TableDef,
)
from arc.domain.project.value_objects import DomainModelSnapshot

logger = logging.getLogger(__name__)

# 字段名 → 列类型推断 (保守映射, 未知默认 text)
_FIELD_TYPE_MAP: dict[str, str] = {
    "id": "uuid",
    "created_at": "timestamptz",
    "updated_at": "timestamptz",
    "deleted_at": "timestamptz",
    "is_active": "boolean",
    "is_deleted": "boolean",
    "status": "text",
}

_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _pluralize(name: str) -> str:
    """简单复数化: Post→posts, Comment→comments, Entity→entities。"""
    lower = name.lower()
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return lower[:-1] + "ies"
    if lower.endswith(("s", "sh", "ch", "x", "z")):
        return lower + "es"
    return lower + "s"


def _infer_column_type(field_name: str) -> str:
    """根据字段名推断 PG 类型, 未知默认 text。"""
    if field_name in _FIELD_TYPE_MAP:
        return _FIELD_TYPE_MAP[field_name]
    if field_name.endswith("_id"):
        return "uuid"
    if field_name.endswith("_at"):
        return "timestamptz"
    if field_name.startswith("is_") or field_name.startswith("has_"):
        return "boolean"
    return "text"


class DomainModelApplier:
    """把 DomainModelSnapshot 同步到 Supabase (经 BaasService)。"""

    def __init__(self, baas_service) -> None:
        self._baas_service = baas_service

    @staticmethod
    def _schema_name_for(project_id: uuid.UUID) -> str:
        """schema_name = arc_ + project_id 前 8 位 hex。"""
        return f"arc_{project_id.hex[:8]}"

    @staticmethod
    def convert_to_baas_schema(
        snapshot: DomainModelSnapshot, *, project_id: uuid.UUID
    ) -> BaasSchema:
        """DomainModelSnapshot.content → BaasSchema (纯转换, 无副作用)。"""
        schema_name = DomainModelApplier._schema_name_for(project_id)
        aggregates = snapshot.content.get("aggregates", []) if isinstance(
            snapshot.content, dict
        ) else []

        tables: list[TableDef] = []
        for agg in aggregates:
            if not isinstance(agg, dict):
                continue
            # LLM 产出 name 可能带中文/括号描述, slugify 取合规标识符片段
            name = DomainModelApplier._slugify_identifier(agg.get("name"))
            if not name:
                continue
            cleaned = {**agg, "name": name}
            tables.append(DomainModelApplier._aggregate_to_table(cleaned))

        # v6.24 P0-2: 默认 RLS 策略 — 有 user_id 行级隔离, 无 user_id authenticated 共享。
        # 之前 policies=[] 导致 RLS 启用但 deny-all (非 superuser 不可读写)。
        policies: list[RlsPolicy] = []
        for table in tables:
            if table.has_rls:
                policies.extend(DomainModelApplier._table_policies(table))

        return BaasSchema(
            schema_name=schema_name,
            tables=tables,
            policies=policies,
            transitions=[],
            actions=[],
        )

    @staticmethod
    def _table_policies(table: TableDef) -> list[RlsPolicy]:
        """为表生成默认 RLS 策略 (符合 rls_validator 期望, 非 deny-all)。

        - 有 user_id: 行级隔离 (user_id = auth.uid()) — 用户只访问自己拥有的行;
        - 无 user_id (字典表): authenticated 共享 — 非 anon 全放行, 非 deny。
        Agent 后续可按需覆盖 (领域模型快照不含业务级 RLS 语义)。
        """
        if any(c.name == "user_id" for c in table.columns):
            expr = "user_id = auth.uid()"
            return [
                RlsPolicy(table.name, "SELECT", "authenticated", using_expr=expr),
                RlsPolicy(table.name, "INSERT", "authenticated", check_expr=expr),
                RlsPolicy(table.name, "UPDATE", "authenticated", using_expr=expr, check_expr=expr),
                RlsPolicy(table.name, "DELETE", "authenticated", using_expr=expr),
            ]
        return [
            RlsPolicy(table.name, "SELECT", "authenticated", using_expr="true"),
            RlsPolicy(table.name, "INSERT", "authenticated", check_expr="true"),
            RlsPolicy(table.name, "UPDATE", "authenticated", using_expr="true", check_expr="true"),
            RlsPolicy(table.name, "DELETE", "authenticated", using_expr="true"),
        ]

    @staticmethod
    def _aggregate_to_table(agg: dict) -> TableDef:
        name = str(agg["name"])
        field_names = agg.get("fields", [])
        if not isinstance(field_names, list):
            field_names = []

        columns: list[ColumnDef] = []
        has_id = False
        for fname in field_names:
            if not isinstance(fname, str) or not _IDENT_RE.fullmatch(fname):
                continue
            if fname == "id":
                has_id = True
            default = (
                "gen_random_uuid()" if fname == "id"
                else "auth.uid()" if fname == "user_id"
                else None
            )
            columns.append(ColumnDef(
                name=fname,
                type=_infer_column_type(fname),
                nullable=fname != "id",
                default=default,
                is_primary=(fname == "id"),
            ))

        # 无 id 字段 → 自动补 UUID 主键
        if not has_id:
            columns.insert(0, ColumnDef(
                name="id", type="uuid", nullable=False,
                default="gen_random_uuid()", is_primary=True,
            ))

        return TableDef(name=_pluralize(name), columns=columns, has_rls=True)

    @staticmethod
    def _slugify_identifier(raw) -> str:
        """从 LLM 产出的 entity name 提取合规 SQL/代码标识符。

        LLM 常产出 ``Order（订单聚合根）`` 这类带中文/括号描述的 name;
        取首个 ``[a-zA-Z_][a-zA-Z0-9_]*`` 片段作表名基础 (如 → ``Order``)。
        纯英文 name (如 ``BaseAggregateRoot``) 原样返回。无合规片段返回 ""。
        v6.24 conversation 端到端实测发现: extractor 不清洗 name, LLM 中文描述
        致 _IDENT_RE 校验失败 → 聚合全跳过 → provision 触发但不建表。
        """
        if not raw:
            return ""
        # _IDENT_RE 带 ^$ 锚定 (fullmatch 用); 这里取首个标识符片段须非锚定
        m = re.search(r"[a-zA-Z_][a-zA-Z0-9_]*", str(raw))
        return m.group(0) if m else ""

    async def apply_snapshot(
        self,
        *,
        project_id: uuid.UUID,
        snapshot: DomainModelSnapshot,
        supabase_url: str,
    ) -> object | None:
        """转换快照并应用到 Supabase。无聚合的空模型跳过。"""
        schema = self.convert_to_baas_schema(
            snapshot, project_id=project_id
        )
        if not schema.tables:
            logger.info(
                "apply_snapshot: 项目 %s 模型 v%d 无聚合, 跳过 BaaS apply",
                project_id, snapshot.version,
            )
            return None

        await self._baas_service.provision(
            project_id=project_id,
            schema_name=schema.schema_name,
            supabase_url=supabase_url,
        )
        return await self._baas_service.apply_model(
            project_id=project_id,
            schema=schema,
            model_version=snapshot.version,
        )
