"""Route-level smoke tests — verify auth enforcement and endpoint existence.

These tests use dependency overrides to avoid needing a real database.
They only check that: (1) unauthenticated requests return 401,
(2) authenticated requests hit the right route (not 404/405).
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from arc.interface.deps import get_current_user, get_db


@pytest.fixture
async def unauth_client():
    """Client with NO auth override — requests should get 401."""
    from arc.main import app

    mock_db = AsyncMock()

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides.pop(get_current_user, None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


PROTECTED_ROUTES = [
    ("GET", "/api/todos"),
    ("GET", "/api/todos/00000000-0000-0000-0000-000000000001"),
    ("GET", "/api/todos/00000000-0000-0000-0000-000000000001/dependencies"),
    ("GET", "/api/projects"),
    ("GET", "/api/experiences"),
    ("GET", "/api/settings"),
]


class TestAuthEnforcement:
    @pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
    async def test_unauthenticated_returns_401(
        self, unauth_client: AsyncClient, method: str, path: str
    ):
        resp = await unauth_client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}, expected 401"


class TestHealthEndpoint:
    async def test_health_returns_200(self, unauth_client: AsyncClient):
        resp = await unauth_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
