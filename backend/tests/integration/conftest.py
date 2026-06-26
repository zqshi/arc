from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from arc.config import settings

TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_session():
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO users (id, username, display_name, is_active, hashed_password) "
                "VALUES (:id, :username, :display_name, true, :pwd) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": str(TEST_USER_ID),
                "username": "test-integration",
                "display_name": "Integration Test User",
                "pwd": "$2b$12$dummy",
            },
        )
        await session.commit()
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from arc.domain.user.entity import User
    from arc.interface.deps import get_current_user, get_db
    from arc.main import app

    test_user = User(
        id=TEST_USER_ID,
        username="test-integration",
        display_name="Integration Test User",
    )

    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    # v6.9: 隔离直用全局 factory 的端点(/health)。原 /health 函数内 import 全局
    # async_session_factory, 不走 get_db override, 受全局 engine 跨 event-loop 连接
    # 污染(unit 全量跑完后连接池异常 → degraded)。替换为复用 db_session 独立 engine
    # 的测试 factory, /health 与全局 engine 解耦, 时序污染不再传导。
    from arc.infrastructure import database as db_module

    @asynccontextmanager
    async def _test_session_factory():
        yield db_session

    monkeypatch.setattr(db_module, "async_session_factory", _test_session_factory)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
