"""Client for the OpenHands AI coding agent REST API.

Provides async methods for session lifecycle management (create, send task,
poll events, stop) with retry logic for transient HTTP failures.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

import httpx

logger = logging.getLogger(__name__)

# Transient HTTP status codes that are safe to retry.
_RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})

# Default retry configuration.
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 1.0  # seconds; doubles each attempt


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class OpenHandsSessionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class OpenHandsEvent:
    """A single event (action / observation / status change) in a session."""

    id: str
    type: str  # action | observation | status
    content: str
    timestamp: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OpenHandsSession:
    """Lightweight handle for an OpenHands conversation."""

    session_id: str
    status: OpenHandsSessionStatus
    workspace: str


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class OpenHandsError(Exception):
    """Base exception for OpenHands client errors."""


class OpenHandsConnectionError(OpenHandsError):
    """Raised when the OpenHands server is unreachable."""


class OpenHandsAPIError(OpenHandsError):
    """Raised when the API returns a non-retryable error."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class OpenHandsClient:
    """Async client for the OpenHands coding-agent REST API.

    Endpoints consumed:
    - ``POST /api/conversations``          -- create session
    - ``GET  /api/conversations/{id}``     -- session status
    - ``POST /api/conversations/{id}/messages`` -- send task
    - ``GET  /api/conversations/{id}/events``   -- poll events
    - ``POST /api/conversations/{id}/stop``     -- stop session
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        *,
        timeout: float = 60.0,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._max_retries = max_retries

        headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers,
        )

    # -- internal helpers -----------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Issue an HTTP request with retry logic for transient failures."""
        import asyncio

        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.request(
                    method, path, json=json, params=params,
                )
            except httpx.ConnectError as exc:
                last_exc = exc
                logger.warning(
                    "OpenHands connection error (attempt %d/%d): %s",
                    attempt + 1, self._max_retries + 1, exc,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(_RETRY_BACKOFF_BASE * (2 ** attempt))
                continue
            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "OpenHands timeout (attempt %d/%d): %s",
                    attempt + 1, self._max_retries + 1, exc,
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(_RETRY_BACKOFF_BASE * (2 ** attempt))
                continue

            if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                logger.warning(
                    "OpenHands retryable status %d (attempt %d/%d)",
                    resp.status_code, attempt + 1, self._max_retries + 1,
                )
                await asyncio.sleep(_RETRY_BACKOFF_BASE * (2 ** attempt))
                continue

            if resp.status_code >= 400:
                detail = resp.text[:500] if resp.text else ""
                raise OpenHandsAPIError(resp.status_code, detail)

            return resp

        # All retries exhausted.
        if last_exc is not None:
            raise OpenHandsConnectionError(
                f"Failed after {self._max_retries + 1} attempts: {last_exc}"
            ) from last_exc
        raise OpenHandsConnectionError("Request failed with no exception captured")

    # -- public API -----------------------------------------------------------

    async def create_session(self, workspace: str = "") -> OpenHandsSession:
        """Create a new OpenHands coding-agent session."""
        resp = await self._request("POST", "/api/conversations", json={"workspace": workspace})
        data = resp.json()
        return OpenHandsSession(
            session_id=data["conversation_id"],
            status=OpenHandsSessionStatus.CREATED,
            workspace=workspace,
        )

    async def send_task(self, session_id: str, task: str) -> None:
        """Send a development task (user message) to the session."""
        if not task or not task.strip():
            raise ValueError("task cannot be empty")
        await self._request(
            "POST",
            f"/api/conversations/{session_id}/messages",
            json={"role": "user", "content": task},
        )

    async def get_status(self, session_id: str) -> OpenHandsSessionStatus:
        """Get the current status of a session."""
        resp = await self._request("GET", f"/api/conversations/{session_id}")
        data = resp.json()
        raw = data.get("status", "created")
        try:
            return OpenHandsSessionStatus(raw)
        except ValueError:
            logger.warning("Unknown OpenHands status: %r, treating as ERROR", raw)
            return OpenHandsSessionStatus.ERROR

    async def get_events(
        self,
        session_id: str,
        since_id: str = "",
    ) -> list[OpenHandsEvent]:
        """Get events (actions, observations, status changes) since *since_id*."""
        params = {"since_id": since_id} if since_id else {}
        resp = await self._request(
            "GET",
            f"/api/conversations/{session_id}/events",
            params=params,
        )
        raw_events = resp.json().get("events", [])
        return [
            OpenHandsEvent(
                id=e["id"],
                type=e.get("type", ""),
                content=e.get("content", ""),
                timestamp=e.get("timestamp", ""),
                metadata=e.get("metadata", {}),
            )
            for e in raw_events
        ]

    async def stop_session(self, session_id: str) -> None:
        """Stop a running session."""
        await self._request("POST", f"/api/conversations/{session_id}/stop")

    # -- lifecycle ------------------------------------------------------------

    async def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> OpenHandsClient:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_openhands_client() -> OpenHandsClient:
    """Create an :class:`OpenHandsClient` from application settings."""
    from arc.config import settings

    return OpenHandsClient(
        base_url=settings.openhands_url,
        api_key=settings.openhands_api_key,
    )
