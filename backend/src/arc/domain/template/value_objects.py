"""DomainTemplate 值对象 (v5.7.0 T1)。"""
from __future__ import annotations

from enum import StrEnum


class TemplateCategory(StrEnum):
    """模板分类 — 对应常见应用领域。"""

    CRUD_APP = "crud_app"  # 博客/CMS/知识库
    WORKFLOW = "workflow"  # 审批/工单/任务管理
    ECOMMERCE = "ecommerce"  # 商城/预约
    SOCIAL = "social"  # 社区/评论
    SAAS_BACKEND = "saas_backend"  # 多租户后台
    CUSTOM = "custom"


class TemplateStatus(StrEnum):
    """模板生命周期状态。

    draft → confirmed → published → deprecated
    """

    DRAFT = "draft"  # 自动提取草稿, 未审核
    CONFIRMED = "confirmed"  # 人工确认可用
    PUBLISHED = "published"  # 发布 (个人/组织可见)
    DEPRECATED = "deprecated"  # 废弃 (终态)


class TemplateScope(StrEnum):
    """模板可见范围。"""

    PERSONAL = "personal"  # 仅创建者
    ORGANIZATION = "organization"  # 团队可见
    PUBLIC = "public"  # 远期: 模板市场


# 状态转换合法性表
VALID_TEMPLATE_TRANSITIONS: dict[TemplateStatus, set[TemplateStatus]] = {
    TemplateStatus.DRAFT: {TemplateStatus.CONFIRMED, TemplateStatus.DEPRECATED},
    TemplateStatus.CONFIRMED: {TemplateStatus.PUBLISHED, TemplateStatus.DEPRECATED},
    TemplateStatus.PUBLISHED: {TemplateStatus.DEPRECATED},
    TemplateStatus.DEPRECATED: set(),  # 终态
}
