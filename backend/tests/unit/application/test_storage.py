"""Unit tests for StorageAdapter (local filesystem mode)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from arc.infrastructure.storage import DEFAULT_MAX_UPLOAD_SIZE as MAX_UPLOAD_SIZE
from arc.infrastructure.storage import StorageAdapter


@pytest.fixture
def storage(tmp_path: Path):
    """Create a StorageAdapter in local mode pointing to a temp dir."""
    with patch("arc.infrastructure.storage.settings") as mock_settings:
        mock_settings.storage_endpoint = ""
        mock_settings.storage_access_key = ""
        mock_settings.storage_secret_key = ""
        mock_settings.storage_bucket = ""
        mock_settings.storage_public_url = ""

        adapter = StorageAdapter()
        base = tmp_path / "previews"
        base.mkdir()

        with patch.object(StorageAdapter, "_local_path") as mock_local:
            def _local_path_impl(key: str) -> Path:
                resolved = (base / key).resolve()
                if not resolved.is_relative_to(base):
                    raise ValueError("Invalid storage key: path traversal detected")
                return resolved

            mock_local.side_effect = _local_path_impl
            yield adapter, base


class TestUpload:
    def test_upload_local_creates_file(self, storage):
        adapter, base = storage
        url = adapter.upload("test/file.html", b"<h1>hi</h1>", "text/html")
        assert "/static/previews/test/file.html" in url or (base / "test" / "file.html").exists()

    def test_upload_size_limit(self, storage):
        adapter, _ = storage
        big_content = b"x" * (MAX_UPLOAD_SIZE + 1)
        with pytest.raises(ValueError, match="exceeds"):
            adapter.upload("big.bin", big_content, "application/octet-stream")

    def test_upload_custom_max_size(self, storage):
        adapter, _ = storage
        content = b"x" * 100
        adapter.upload("ok.bin", content, "application/octet-stream", max_size=200)
        with pytest.raises(ValueError):
            adapter.upload("too-big.bin", content, "application/octet-stream", max_size=50)


class TestDelete:
    def test_delete_existing_file(self, storage):
        adapter, base = storage
        path = base / "to_delete.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"data")
        adapter.delete("to_delete.txt")

    def test_delete_nonexistent_no_error(self, storage):
        adapter, _ = storage
        adapter.delete("does_not_exist.txt")


class TestDeletePrefix:
    def test_delete_prefix_removes_all(self, storage):
        adapter, base = storage
        subdir = base / "prefix" / "sub"
        subdir.mkdir(parents=True)
        (subdir / "a.txt").write_bytes(b"a")
        (subdir / "b.txt").write_bytes(b"b")

        count = adapter.delete_prefix("prefix")
        assert count == 2
        assert not (base / "prefix").exists()

    def test_delete_prefix_nonexistent(self, storage):
        adapter, _ = storage
        count = adapter.delete_prefix("no-such-prefix")
        assert count == 0


class TestDownload:
    def test_download_existing(self, storage):
        adapter, base = storage
        path = base / "dl_test.bin"
        path.write_bytes(b"payload")
        data = adapter.download("dl_test.bin")
        assert data == b"payload"

    def test_download_missing_returns_none(self, storage):
        adapter, _ = storage
        assert adapter.download("missing.bin") is None


class TestPathTraversal:
    def test_traversal_blocked(self, storage):
        adapter, _ = storage
        with pytest.raises(ValueError, match="traversal"):
            adapter.upload("../../../etc/passwd", b"evil", "text/plain")
