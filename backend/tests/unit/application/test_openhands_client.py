"""Unit tests for arc.application.ai.openhands_client.

Uses httpx.MockTransport to intercept outgoing requests -- no real network
calls are made.
"""

from __future__ import annotations

import json

import httpx
import pytest

from arc.application.ai.openhands_client import (
    OpenHandsAPIError,
    OpenHandsClient,
    OpenHandsEvent,
    OpenHandsSession,
    OpenHandsSessionStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_response(data: dict, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
    )


def _make_client(handler) -> OpenHandsClient:
    """Build an OpenHandsClient whose internal httpx client uses *handler*."""
    transport = httpx.MockTransport(handler)
    client = OpenHandsClient(base_url="http://openhands.test", api_key="test-key", max_retries=0)
    # Replace the internal client with one backed by the mock transport
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="http://openhands.test",
        headers={"Authorization": "Bearer test-key"},
    )
    return client


def _make_client_with_retries(handler, max_retries: int = 2) -> OpenHandsClient:
    """Build a client with retries enabled, using mock transport."""
    transport = httpx.MockTransport(handler)
    client = OpenHandsClient(
        base_url="http://openhands.test", api_key="test-key", max_retries=max_retries,
    )
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="http://openhands.test",
        headers={"Authorization": "Bearer test-key"},
    )
    return client


# ---------------------------------------------------------------------------
# Session status enum
# ---------------------------------------------------------------------------

class TestOpenHandsSessionStatus:
    def test_all_values(self) -> None:
        assert OpenHandsSessionStatus.CREATED == "created"
        assert OpenHandsSessionStatus.RUNNING == "running"
        assert OpenHandsSessionStatus.COMPLETED == "completed"
        assert OpenHandsSessionStatus.ERROR == "error"
        assert OpenHandsSessionStatus.PAUSED == "paused"


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------

class TestCreateSession:
    async def test_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert str(request.url).endswith("/api/conversations")
            body = json.loads(request.content)
            assert body["workspace"] == "/code"
            return _json_response({"conversation_id": "sess-001"})

        client = _make_client(handler)
        session = await client.create_session(workspace="/code")

        assert isinstance(session, OpenHandsSession)
        assert session.session_id == "sess-001"
        assert session.status == OpenHandsSessionStatus.CREATED
        assert session.workspace == "/code"
        await client.close()

    async def test_empty_workspace(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response({"conversation_id": "sess-002"})

        client = _make_client(handler)
        session = await client.create_session()
        assert session.session_id == "sess-002"
        assert session.workspace == ""
        await client.close()


# ---------------------------------------------------------------------------
# send_task
# ---------------------------------------------------------------------------

class TestSendTask:
    async def test_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "/messages" in str(request.url)
            body = json.loads(request.content)
            assert body == {"role": "user", "content": "Fix the bug"}
            return _json_response({"ok": True})

        client = _make_client(handler)
        await client.send_task("sess-001", "Fix the bug")
        await client.close()

    async def test_empty_task_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response({})

        client = _make_client(handler)
        with pytest.raises(ValueError, match="task cannot be empty"):
            await client.send_task("sess-001", "")
        with pytest.raises(ValueError, match="task cannot be empty"):
            await client.send_task("sess-001", "   ")
        await client.close()


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    async def test_running(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response({"status": "running"})

        client = _make_client(handler)
        status = await client.get_status("sess-001")
        assert status == OpenHandsSessionStatus.RUNNING
        await client.close()

    async def test_completed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response({"status": "completed"})

        client = _make_client(handler)
        status = await client.get_status("sess-001")
        assert status == OpenHandsSessionStatus.COMPLETED
        await client.close()

    async def test_missing_status_defaults_to_created(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response({})

        client = _make_client(handler)
        status = await client.get_status("sess-001")
        assert status == OpenHandsSessionStatus.CREATED
        await client.close()

    async def test_unknown_status_returns_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response({"status": "exploded"})

        client = _make_client(handler)
        status = await client.get_status("sess-001")
        assert status == OpenHandsSessionStatus.ERROR
        await client.close()


# ---------------------------------------------------------------------------
# get_events
# ---------------------------------------------------------------------------

class TestGetEvents:
    async def test_returns_events(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response({
                "events": [
                    {
                        "id": "e1",
                        "type": "action",
                        "content": "Running ls",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "metadata": {"tool": "bash"},
                    },
                    {
                        "id": "e2",
                        "type": "observation",
                        "content": "file.py",
                        "timestamp": "2025-01-01T00:00:01Z",
                    },
                ],
            })

        client = _make_client(handler)
        events = await client.get_events("sess-001")

        assert len(events) == 2
        assert isinstance(events[0], OpenHandsEvent)
        assert events[0].id == "e1"
        assert events[0].type == "action"
        assert events[0].metadata == {"tool": "bash"}
        assert events[1].metadata == {}
        await client.close()

    async def test_since_id_param(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert "since_id=e5" in str(request.url)
            return _json_response({"events": []})

        client = _make_client(handler)
        events = await client.get_events("sess-001", since_id="e5")
        assert events == []
        await client.close()

    async def test_empty_events(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response({"events": []})

        client = _make_client(handler)
        events = await client.get_events("sess-001")
        assert events == []
        await client.close()


# ---------------------------------------------------------------------------
# stop_session
# ---------------------------------------------------------------------------

class TestStopSession:
    async def test_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert "/stop" in str(request.url)
            return _json_response({"ok": True})

        client = _make_client(handler)
        await client.stop_session("sess-001")  # no exception == success
        await client.close()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    async def test_4xx_raises_api_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=404, text="Not Found")

        client = _make_client(handler)
        with pytest.raises(OpenHandsAPIError) as exc_info:
            await client.get_status("nonexistent")
        assert exc_info.value.status_code == 404
        await client.close()

    async def test_auth_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=401, text="Unauthorized")

        client = _make_client(handler)
        with pytest.raises(OpenHandsAPIError) as exc_info:
            await client.create_session()
        assert exc_info.value.status_code == 401
        await client.close()


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

class TestRetryLogic:
    async def test_retries_on_503_then_succeeds(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(status_code=503, text="Unavailable")
            return _json_response({"conversation_id": "sess-retry"})

        client = _make_client_with_retries(handler, max_retries=3)
        session = await client.create_session()
        assert session.session_id == "sess-retry"
        assert call_count == 3
        await client.close()

    async def test_exhausts_retries_on_persistent_503(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=503, text="Down")

        # max_retries=1 means 2 total attempts
        client = _make_client_with_retries(handler, max_retries=1)
        with pytest.raises(OpenHandsAPIError) as exc_info:
            await client.get_status("sess-001")
        assert exc_info.value.status_code == 503
        await client.close()

    async def test_no_retry_on_400(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(status_code=400, text="Bad Request")

        client = _make_client_with_retries(handler, max_retries=3)
        with pytest.raises(OpenHandsAPIError) as exc_info:
            await client.create_session()
        assert exc_info.value.status_code == 400
        assert call_count == 1  # no retries for 400
        await client.close()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    async def test_async_context_manager(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _json_response({"conversation_id": "sess-cm"})

        transport = httpx.MockTransport(handler)
        async with OpenHandsClient(
            base_url="http://openhands.test", api_key="k",
        ) as client:
            client._client = httpx.AsyncClient(
                transport=transport,
                base_url="http://openhands.test",
            )
            session = await client.create_session()
            assert session.session_id == "sess-cm"


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

class TestHeaders:
    def test_auth_header_present_when_api_key_set(self) -> None:
        client = OpenHandsClient(base_url="http://test", api_key="my-key")
        assert client._client.headers["Authorization"] == "Bearer my-key"

    def test_no_auth_header_when_empty_key(self) -> None:
        client = OpenHandsClient(base_url="http://test", api_key="")
        assert "Authorization" not in client._client.headers
