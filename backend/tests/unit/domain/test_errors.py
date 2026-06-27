"""domain/errors 错误体系单元测试 (v6.11 T5)。

验证领域错误不含 HTTP 语义泄漏: DomainError 纯业务异常, AppError 携带 error_code/
status_code 供 route 层转译, 各子类默认状态码与 error_code 正确。
"""

from __future__ import annotations

import pytest

from arc.domain.errors import (
    AppError,
    AuthenticationError,
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
)


class TestDomainError:
    def test_is_exception(self):
        assert issubclass(DomainError, Exception)

    def test_detail_stored(self):
        e = DomainError("boom")
        assert e.detail == "boom"
        assert str(e) == "boom"

    def test_no_status_code_attribute(self):
        """DomainError 纯领域异常, 不应携带 HTTP status_code。"""
        e = DomainError("x")
        assert not hasattr(e, "status_code")


class TestAppError:
    def test_defaults(self):
        e = AppError("msg")
        assert e.detail == "msg"
        assert e.error_code == "APP_ERROR"
        assert e.status_code == 400

    def test_custom_code_and_status(self):
        e = AppError("msg", error_code="CUSTOM", status_code=418)
        assert e.error_code == "CUSTOM"
        assert e.status_code == 418


class TestErrorSubclasses:
    def test_not_found_defaults(self):
        e = NotFoundError()
        assert e.status_code == 404
        assert e.error_code == "NOT_FOUND"
        assert "不存在" in e.detail

    def test_not_found_custom_detail(self):
        e = NotFoundError("项目不存在")
        assert e.detail == "项目不存在"
        assert e.status_code == 404

    def test_authentication_defaults(self):
        e = AuthenticationError()
        assert e.status_code == 401
        assert e.error_code == "AUTHENTICATION_ERROR"

    def test_forbidden_defaults(self):
        e = ForbiddenError()
        assert e.status_code == 403
        assert e.error_code == "FORBIDDEN"

    def test_conflict_defaults(self):
        e = ConflictError()
        assert e.status_code == 409
        assert e.error_code == "CONFLICT"

    def test_all_subclass_app_error(self):
        for cls in (NotFoundError, AuthenticationError, ForbiddenError, ConflictError):
            assert issubclass(cls, AppError)
            assert issubclass(cls, Exception)

    @pytest.mark.parametrize("cls,expected_status", [
        (NotFoundError, 404),
        (AuthenticationError, 401),
        (ForbiddenError, 403),
        (ConflictError, 409),
    ])
    def test_status_code_mapping(self, cls, expected_status):
        assert cls().status_code == expected_status
