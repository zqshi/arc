from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from arc.config import settings


class SMSService:
    _instance: SMSService | None = None

    def __init__(self):
        self._codes: dict[str, tuple[str, datetime]] = {}

    @classmethod
    def get_instance(cls) -> SMSService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def send_code(self, phone: str) -> str:
        if settings.sms_mock_mode:
            code = "666666"
        else:
            code = str(random.randint(100000, 999999))
            # TODO: 对接短信网关（阿里云/腾讯云）
        expire = datetime.now(UTC) + timedelta(minutes=5)
        self._codes[phone] = (code, expire)
        return code

    async def verify_code(self, phone: str, code: str) -> bool:
        stored = self._codes.get(phone)
        if not stored:
            return False
        stored_code, expire = stored
        if datetime.now(UTC) > expire:
            del self._codes[phone]
            return False
        if stored_code != code:
            return False
        del self._codes[phone]
        return True
