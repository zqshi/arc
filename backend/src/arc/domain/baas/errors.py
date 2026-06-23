"""BaaS 领域错误 (v5.6.0)。

不含 HTTP 状态码，纯业务语义。infrastructure/interface 层捕获后映射为 HTTPException。
"""
from arc.domain.errors import DomainError


class ProvisionError(DomainError):
    """Supabase schema provision 失败 (连接/创建 schema/元模型初始化)。"""


class SchemaApplyError(DomainError):
    """DomainModelSnapshot → Supabase 应用失败 (字段冲突/破坏性变更/SQL 执行错误)。"""


class RlsValidationError(DomainError):
    """Agent 生成的 RLS 策略有安全漏洞 (user_id DEFAULT 缺失等)。

    v5.6.0 不阻断，仅 WARNING + 人工审批 gate (见 rls_validator.py)。
    """
