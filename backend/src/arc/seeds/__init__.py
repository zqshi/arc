"""Seed data management — demo accounts and full-chain sample data.

All seed logic is centralised here. Called from main.py lifespan on DEBUG startup.
"""
from __future__ import annotations

import logging

from arc.config import settings

logger = logging.getLogger(__name__)

SEED_ACCOUNTS = [
    {"username": "demo", "password": "demo123", "display_name": "Demo 用户"},
    {"username": "test", "password": "test123", "display_name": "测试用户"},
]


async def ensure_seed_users() -> None:
    """Create default test accounts and sample data on first startup (debug only)."""
    if not settings.debug:
        return
    try:
        from arc.application.auth.password import hash_password
        from arc.domain.user.entity import User
        from arc.infrastructure.database import async_session_factory
        from arc.infrastructure.repositories.project import ProjectRepository
        from arc.infrastructure.repositories.user import UserRepository

        async with async_session_factory() as db:
            user_repo = UserRepository(db)
            for acct in SEED_ACCOUNTS:
                existing = await user_repo.get_by_username(acct["username"])
                if existing:
                    continue
                user = User(
                    username=acct["username"],
                    hashed_password=hash_password(acct["password"]),
                    display_name=acct["display_name"],
                )
                await user_repo.create(user)
                logger.info("Seed user created: %s", acct["username"])
            await db.commit()

            proj_repo = ProjectRepository(db)
            for acct in SEED_ACCOUNTS:
                u = await user_repo.get_by_username(acct["username"])
                if not u:
                    continue
                existing = await proj_repo.list_all(user_id=u.id)
                if existing:
                    continue
                await _create_seed_data(db, u.id)
                await db.commit()
                logger.info("Seed demo data created for user: %s", acct["username"])
    except Exception as exc:
        logger.warning("Seed user creation failed: %s", exc)


async def _create_seed_data(db, user_id) -> None:  # type: ignore[no-untyped-def]
    from .data import create_seed_data

    await create_seed_data(db, user_id)
