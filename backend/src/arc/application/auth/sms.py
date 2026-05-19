from __future__ import annotations

import random
import time
from datetime import UTC, datetime, timedelta

from arc.config import settings
from arc.domain.errors import AppError

_SEND_INTERVAL_SECONDS = 60
_MAX_SENDS_PER_HOUR = 5
_MAX_VERIFY_FAILURES = 5
_LOCKOUT_SECONDS = 1800


class RateLimitedError(AppError):
    def __init__(self, detail: str = "操作过于频繁，请稍后再试"):
        super().__init__(detail, error_code="RATE_LIMITED", status_code=429)


class SMSService:
    """In-memory SMS service. Sufficient for single-instance deployment.
    For multi-instance, replace _codes/_send_log/_fail_log with Redis."""

    _instance: SMSService | None = None

    def __init__(self):
        self._codes: dict[str, tuple[str, datetime]] = {}
        self._send_log: dict[str, list[float]] = {}
        self._fail_log: dict[str, tuple[int, float]] = {}

    @classmethod
    def get_instance(cls) -> SMSService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _check_send_rate(self, phone: str) -> None:
        now = time.monotonic()
        log = self._send_log.get(phone, [])
        log = [t for t in log if now - t < 3600]
        self._send_log[phone] = log

        if log and now - log[-1] < _SEND_INTERVAL_SECONDS:
            wait = int(_SEND_INTERVAL_SECONDS - (now - log[-1]))
            raise RateLimitedError(f"发送过于频繁，请 {wait} 秒后重试")

        if len(log) >= _MAX_SENDS_PER_HOUR:
            raise RateLimitedError("1 小时内发送次数已达上限，请稍后再试")

    def _check_verify_lockout(self, phone: str) -> None:
        record = self._fail_log.get(phone)
        if not record:
            return
        failures, locked_at = record
        if failures >= _MAX_VERIFY_FAILURES:
            elapsed = time.monotonic() - locked_at
            if elapsed < _LOCKOUT_SECONDS:
                remain = int((_LOCKOUT_SECONDS - elapsed) / 60)
                raise RateLimitedError(f"验证失败次数过多，请 {remain} 分钟后再试")
            del self._fail_log[phone]

    def _record_verify_failure(self, phone: str) -> None:
        record = self._fail_log.get(phone)
        if record:
            self._fail_log[phone] = (record[0] + 1, time.monotonic())
        else:
            self._fail_log[phone] = (1, time.monotonic())

    def _clear_verify_failures(self, phone: str) -> None:
        self._fail_log.pop(phone, None)

    async def send_code(self, phone: str) -> str:
        self._check_send_rate(phone)

        if settings.sms_mock_mode:
            code = "666666"
        else:
            code = str(random.randint(100000, 999999))

        expire = datetime.now(UTC) + timedelta(minutes=5)
        self._codes[phone] = (code, expire)

        self._send_log.setdefault(phone, []).append(time.monotonic())
        return code

    async def verify_code(self, phone: str, code: str) -> bool:
        self._check_verify_lockout(phone)

        stored = self._codes.get(phone)
        if not stored:
            self._record_verify_failure(phone)
            return False

        stored_code, expire = stored
        if datetime.now(UTC) > expire:
            del self._codes[phone]
            self._record_verify_failure(phone)
            return False

        if stored_code != code:
            self._record_verify_failure(phone)
            return False

        del self._codes[phone]
        self._clear_verify_failures(phone)
        return True
