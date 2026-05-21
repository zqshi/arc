from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from arc.domain.user.value_objects import UserRole


@dataclass
class User:
    display_name: str
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    username: str | None = None
    phone: str | None = None
    hashed_password: str | None = None
    is_active: bool = True
    role: UserRole = UserRole.ADMIN
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
