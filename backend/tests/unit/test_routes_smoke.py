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

FAKE_UUID = "00000000-0000-0000-0000-000000000001"
FAKE_UUID2 = "00000000-0000-0000-0000-000000000002"


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
    # Todos
    ("GET", "/api/todos"),
    ("GET", f"/api/todos/{FAKE_UUID}"),
    ("GET", f"/api/todos/{FAKE_UUID}/dependencies"),
    ("POST", f"/api/todos/{FAKE_UUID}/dependencies"),
    ("DELETE", f"/api/todos/{FAKE_UUID}/dependencies/{FAKE_UUID2}"),
    ("POST", "/api/todos"),
    ("PUT", f"/api/todos/{FAKE_UUID}"),
    ("DELETE", f"/api/todos/{FAKE_UUID}"),
    ("POST", f"/api/todos/{FAKE_UUID}/extract-tags"),
    ("GET", f"/api/todos/{FAKE_UUID}/conversations"),
    ("POST", f"/api/todos/{FAKE_UUID}/start-conversation"),
    ("GET", f"/api/todos/{FAKE_UUID}/deliverables"),
    ("POST", f"/api/todos/{FAKE_UUID}/quick-message"),
    # Pipeline
    ("GET", f"/api/todos/{FAKE_UUID}/pipeline"),
    ("POST", f"/api/todos/{FAKE_UUID}/pipeline/start"),
    ("POST", f"/api/todos/{FAKE_UUID}/phases/requirement/start"),
    ("POST", f"/api/todos/{FAKE_UUID}/phases/requirement/generate"),
    ("POST", f"/api/todos/{FAKE_UUID}/phases/requirement/confirm"),
    ("POST", f"/api/todos/{FAKE_UUID}/phases/requirement/skip"),
    ("POST", f"/api/todos/{FAKE_UUID}/pipeline/rollback"),
    ("GET", f"/api/todos/{FAKE_UUID}/artifacts"),
    ("GET", f"/api/todos/{FAKE_UUID}/artifacts/{FAKE_UUID2}"),
    ("PUT", f"/api/todos/{FAKE_UUID}/artifacts/{FAKE_UUID2}"),
    ("POST", f"/api/todos/{FAKE_UUID}/artifacts/{FAKE_UUID2}/confirm"),
    # Agent
    ("POST", f"/api/todos/{FAKE_UUID}/phases/requirement/execute"),
    ("GET", f"/api/todos/{FAKE_UUID}/phases/requirement/agent-session"),
    ("POST", f"/api/todos/{FAKE_UUID}/phases/requirement/cancel-agent"),
    ("GET", f"/api/todos/{FAKE_UUID}/phases/requirement/agent-events"),
    ("GET", "/api/todos/agent-types"),
    # Projects
    ("GET", "/api/projects"),
    ("POST", "/api/projects"),
    ("GET", f"/api/projects/{FAKE_UUID}"),
    ("PATCH", f"/api/projects/{FAKE_UUID}"),
    ("DELETE", f"/api/projects/{FAKE_UUID}"),
    ("POST", f"/api/projects/{FAKE_UUID}/archive"),
    ("POST", f"/api/projects/{FAKE_UUID}/scan-codebase"),
    ("GET", f"/api/projects/{FAKE_UUID}/scan-codebase/stream"),
    ("POST", f"/api/projects/{FAKE_UUID}/batch-start-conversations"),
    ("GET", f"/api/projects/{FAKE_UUID}/task-stream"),
    ("GET", f"/api/projects/{FAKE_UUID}/members"),
    ("POST", f"/api/projects/{FAKE_UUID}/members"),
    ("PATCH", f"/api/projects/{FAKE_UUID}/members/{FAKE_UUID2}"),
    ("DELETE", f"/api/projects/{FAKE_UUID}/members/{FAKE_UUID2}"),
    ("GET", f"/api/projects/{FAKE_UUID}/mode-switch-impact"),
    # Versions
    ("GET", f"/api/projects/{FAKE_UUID}/versions"),
    ("POST", f"/api/projects/{FAKE_UUID}/versions"),
    ("PATCH", f"/api/projects/{FAKE_UUID}/versions/{FAKE_UUID2}"),
    ("POST", f"/api/projects/{FAKE_UUID}/versions/{FAKE_UUID2}/activate"),
    ("POST", f"/api/projects/{FAKE_UUID}/versions/{FAKE_UUID2}/release"),
    ("DELETE", f"/api/projects/{FAKE_UUID}/versions/{FAKE_UUID2}"),
    # Project experiences
    ("GET", f"/api/projects/{FAKE_UUID}/experiences"),
    ("GET", f"/api/projects/{FAKE_UUID}/experience-insights"),
    # Project documents
    ("POST", f"/api/projects/{FAKE_UUID}/documents"),
    ("GET", f"/api/projects/{FAKE_UUID}/documents"),
    ("DELETE", f"/api/projects/{FAKE_UUID}/documents/{FAKE_UUID2}"),
    # Planning sessions
    ("POST", f"/api/projects/{FAKE_UUID}/planning-sessions"),
    ("GET", f"/api/projects/{FAKE_UUID}/planning-sessions"),
    ("POST", f"/api/projects/{FAKE_UUID}/planning-sessions/{FAKE_UUID2}/generate"),
    ("POST", f"/api/projects/{FAKE_UUID}/planning-sessions/{FAKE_UUID2}/confirm"),
    ("POST", f"/api/projects/{FAKE_UUID}/planning-sessions/{FAKE_UUID2}/apply"),
    ("POST", f"/api/projects/{FAKE_UUID}/planning-sessions/{FAKE_UUID2}/preview-diff"),
    ("POST", f"/api/projects/{FAKE_UUID}/planning-sessions/{FAKE_UUID2}/apply-with-diff"),
    ("POST", f"/api/projects/{FAKE_UUID}/planning-sessions/{FAKE_UUID2}/revise"),
    ("GET", f"/api/projects/{FAKE_UUID}/versions/{FAKE_UUID2}/planning-sessions"),
    ("POST", f"/api/projects/{FAKE_UUID}/versions/{FAKE_UUID2}/analyze"),
    # Experiences
    ("GET", "/api/experiences"),
    ("GET", "/api/experiences/search"),
    ("GET", "/api/experiences/analytics/reuse"),
    ("GET", f"/api/experiences/{FAKE_UUID}"),
    ("POST", "/api/experiences"),
    ("PATCH", f"/api/experiences/{FAKE_UUID}"),
    ("POST", f"/api/experiences/{FAKE_UUID}/confirm"),
    ("POST", f"/api/experiences/{FAKE_UUID}/archive"),
    ("POST", f"/api/experiences/{FAKE_UUID}/promote"),
    ("POST", f"/api/experiences/{FAKE_UUID}/distill"),
    ("POST", f"/api/experiences/{FAKE_UUID}/feedback"),
    # Conversations
    ("GET", f"/api/conversations/{FAKE_UUID}"),
    ("POST", f"/api/conversations/{FAKE_UUID}/messages"),
    # Settings
    ("GET", "/api/settings"),
    # Filesystem
    ("GET", "/api/filesystem/browse"),
    ("POST", "/api/filesystem/mkdir"),
    # Auth (protected)
    ("GET", "/api/auth/me"),
]

PUBLIC_ROUTES = [
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/sms/send"),
    ("POST", "/api/auth/sms/login"),
    ("POST", "/api/auth/refresh"),
]


class TestAuthEnforcement:
    @pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
    async def test_unauthenticated_returns_401(
        self, unauth_client: AsyncClient, method: str, path: str
    ):
        resp = await unauth_client.request(method, path)
        assert resp.status_code == 401, f"{method} {path} returned {resp.status_code}, expected 401"


class TestPublicRoutes:
    @pytest.mark.parametrize("method,path", PUBLIC_ROUTES)
    async def test_public_routes_not_404(
        self, unauth_client: AsyncClient, method: str, path: str
    ):
        resp = await unauth_client.request(method, path)
        assert resp.status_code != 404, f"{method} {path} returned 404 — route not mounted"
        assert resp.status_code != 405, f"{method} {path} returned 405 — method not allowed"


class TestHealthEndpoint:
    async def test_health_returns_200(self, unauth_client: AsyncClient):
        resp = await unauth_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
