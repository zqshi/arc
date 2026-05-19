from __future__ import annotations


class AppError(Exception):
    def __init__(
        self, detail: str, error_code: str = "APP_ERROR", status_code: int = 400
    ):
        self.detail = detail
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(detail)


class NotFoundError(AppError):
    def __init__(self, detail: str = "资源不存在"):
        super().__init__(detail, error_code="NOT_FOUND", status_code=404)


class AuthenticationError(AppError):
    def __init__(self, detail: str = "认证失败"):
        super().__init__(detail, error_code="AUTHENTICATION_ERROR", status_code=401)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "无权限"):
        super().__init__(detail, error_code="FORBIDDEN", status_code=403)


class ConflictError(AppError):
    def __init__(self, detail: str = "资源冲突"):
        super().__init__(detail, error_code="CONFLICT", status_code=409)
