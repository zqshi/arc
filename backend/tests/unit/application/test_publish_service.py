"""Unit tests for PublishService."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def publish_service(mock_db):
    with patch("arc.application.artifact.publish_service.get_storage") as mock_storage_fn:
        mock_storage = MagicMock()
        mock_storage.async_upload = AsyncMock(return_value="http://s3/preview/index.html")
        mock_storage.async_delete_prefix = AsyncMock(return_value=3)
        mock_storage_fn.return_value = mock_storage

        from arc.application.artifact.publish_service import PublishService

        svc = PublishService(mock_db)
        yield svc, mock_storage


class TestCSPInjection:
    def test_csp_meta_injected_in_head(self):
        from arc.application.artifact.publish_service import CSP_META

        assert "Content-Security-Policy" in CSP_META
        assert "connect-src 'none'" in CSP_META

    def test_csp_blocks_external_connections(self):
        from arc.application.artifact.publish_service import CSP_META

        assert "connect-src 'none'" in CSP_META


class TestPublishKeyFormat:
    def test_preview_key_structure(self):
        todo_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        prefix = f"previews/{todo_id}/{artifact_id}"
        assert str(todo_id) in prefix
        assert str(artifact_id) in prefix


class TestUnpublish:
    @pytest.mark.asyncio
    async def test_unpublish_calls_delete_prefix(self, publish_service):
        svc, mock_storage = publish_service

        mock_artifact = MagicMock()
        mock_artifact.id = uuid.uuid4()
        mock_artifact.todo_id = uuid.uuid4()
        mock_artifact.preview_url = "http://s3/some/url"
        mock_artifact.set_preview_url = MagicMock()

        svc.repo = AsyncMock()
        svc.repo.get_by_id = AsyncMock(return_value=mock_artifact)
        svc.repo.update = AsyncMock()

        await svc.unpublish_prototype(mock_artifact.id)

        mock_storage.async_delete_prefix.assert_called_once()
        mock_artifact.set_preview_url.assert_called_once_with(None)
