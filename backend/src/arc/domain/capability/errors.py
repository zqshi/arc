"""能力注册表领域错误 (v6.8.0 W1)。

不含 HTTP 状态码，纯业务语义。infrastructure/interface 层捕获后映射为 HTTPException。
"""
from arc.domain.errors import DomainError


class CapabilityError(DomainError):
    """能力声明相关领域错误 (空名/类型非法/状态转换非法)。"""
