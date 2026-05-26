"""Unit tests for DocumentService."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def doc_service(mock_db):
    with patch("arc.application.planning.document_service.get_storage") as mock_storage_fn:
        mock_storage = MagicMock()
        mock_storage.async_upload = AsyncMock(return_value="http://s3/key")
        mock_storage.async_delete = AsyncMock()
        mock_storage_fn.return_value = mock_storage

        from arc.application.planning.document_service import DocumentService

        svc = DocumentService(mock_db)
        svc._storage = mock_storage
        yield svc, mock_storage


class TestSanitizeFilename:
    def test_normal_filename(self):
        from arc.application.planning.document_service import _sanitize_filename

        assert _sanitize_filename("report.pdf") == "report.pdf"

    def test_path_traversal(self):
        from arc.application.planning.document_service import _sanitize_filename

        assert _sanitize_filename("../../etc/passwd") == "passwd"

    def test_nested_path(self):
        from arc.application.planning.document_service import _sanitize_filename

        assert _sanitize_filename("foo/bar/baz.txt") == "baz.txt"

    def test_dot_rejected(self):
        from arc.application.planning.document_service import _sanitize_filename

        with pytest.raises(ValueError, match="Invalid filename"):
            _sanitize_filename(".")

    def test_dotdot_rejected(self):
        from arc.application.planning.document_service import _sanitize_filename

        with pytest.raises(ValueError, match="Invalid filename"):
            _sanitize_filename("..")

    def test_empty_rejected(self):
        from arc.application.planning.document_service import _sanitize_filename

        with pytest.raises(ValueError, match="Invalid filename"):
            _sanitize_filename("")


class TestStorageKey:
    def test_key_format(self):
        from arc.application.planning.document_service import _storage_key

        project_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        key = _storage_key(project_id, doc_id, "my_doc.pdf")
        assert key == f"documents/{project_id}/{doc_id}/my_doc.pdf"


class TestUploadValidation:
    @pytest.mark.asyncio
    async def test_reject_unsupported_content_type(self, doc_service):
        svc, _ = doc_service
        with pytest.raises(ValueError, match="不支持的文件类型"):
            await svc.upload(uuid.uuid4(), "test.exe", "application/x-executable", b"data")

    @pytest.mark.asyncio
    async def test_reject_oversize_file(self, doc_service):
        svc, _ = doc_service
        big = b"x" * (21 * 1024 * 1024)
        with pytest.raises(ValueError, match="20MB"):
            await svc.upload(uuid.uuid4(), "big.pdf", "application/pdf", big)

    @pytest.mark.asyncio
    async def test_allowed_content_types(self, doc_service):
        from arc.application.planning.document_service import ALLOWED_CONTENT_TYPES

        assert "application/pdf" in ALLOWED_CONTENT_TYPES
        assert "text/markdown" in ALLOWED_CONTENT_TYPES
        assert "text/plain" in ALLOWED_CONTENT_TYPES
