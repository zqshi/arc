"""S3-compatible object storage adapter with local filesystem fallback."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from arc.config import settings

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2 MB


class StorageAdapter:
    """Upload/delete objects via S3-compatible API or local filesystem."""

    def __init__(self):
        self._client = None
        self._is_s3 = bool(settings.storage_endpoint)

        if self._is_s3:
            import boto3
            from botocore.config import Config as BotoConfig

            self._client = boto3.client(
                "s3",
                endpoint_url=settings.storage_endpoint,
                aws_access_key_id=settings.storage_access_key,
                aws_secret_access_key=settings.storage_secret_key,
                config=BotoConfig(signature_version="s3v4"),
                region_name="us-east-1",
            )
            self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=settings.storage_bucket)
        except Exception:
            try:
                self._client.create_bucket(Bucket=settings.storage_bucket)
                self._client.put_bucket_policy(
                    Bucket=settings.storage_bucket,
                    Policy=f'{{"Version":"2012-10-17","Statement":[{{"Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::{settings.storage_bucket}/*"}}]}}',
                )
                logger.info("Created bucket: %s", settings.storage_bucket)
            except Exception as e:
                logger.warning("Failed to create bucket %s: %s", settings.storage_bucket, e)

    def upload(
        self, key: str, content: bytes, content_type: str = "text/html",
        *, max_size: int = MAX_UPLOAD_SIZE,
    ) -> str:
        if len(content) > max_size:
            raise ValueError(f"Upload exceeds {max_size} bytes limit ({len(content)} bytes)")
        if self._is_s3:
            return self._upload_s3(key, content, content_type)
        return self._upload_local(key, content, content_type)

    async def async_upload(
        self, key: str, content: bytes, content_type: str = "text/html",
        *, max_size: int = MAX_UPLOAD_SIZE,
    ) -> str:
        return await asyncio.to_thread(self.upload, key, content, content_type, max_size=max_size)

    def delete(self, key: str) -> None:
        if self._is_s3:
            self._client.delete_object(Bucket=settings.storage_bucket, Key=key)
        else:
            path = self._local_path(key)
            if path.exists():
                path.unlink()

    async def async_delete(self, key: str) -> None:
        await asyncio.to_thread(self.delete, key)

    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects under a key prefix. Returns count of deleted objects."""
        if self._is_s3:
            return self._delete_prefix_s3(prefix)
        return self._delete_prefix_local(prefix)

    async def async_delete_prefix(self, prefix: str) -> int:
        return await asyncio.to_thread(self.delete_prefix, prefix)

    def download(self, key: str) -> bytes | None:
        """Download object content. Returns None if not found."""
        if self._is_s3:
            return self._download_s3(key)
        return self._download_local(key)

    async def async_download(self, key: str) -> bytes | None:
        return await asyncio.to_thread(self.download, key)

    def _download_s3(self, key: str) -> bytes | None:
        try:
            resp = self._client.get_object(Bucket=settings.storage_bucket, Key=key)
            return resp["Body"].read()
        except self._client.exceptions.NoSuchKey:
            return None
        except Exception:
            return None

    def _download_local(self, key: str) -> bytes | None:
        path = self._local_path(key)
        if not path.exists():
            return None
        return path.read_bytes()

    def _delete_prefix_s3(self, prefix: str) -> int:
        deleted = 0
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=settings.storage_bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if not objects:
                continue
            self._client.delete_objects(
                Bucket=settings.storage_bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
            )
            deleted += len(objects)
        return deleted

    def _delete_prefix_local(self, prefix: str) -> int:
        base = self._local_path(prefix)
        if not base.exists():
            return 0
        deleted = 0
        for f in base.rglob("*"):
            if f.is_file():
                f.unlink()
                deleted += 1
        if base.is_dir():
            import shutil
            shutil.rmtree(base, ignore_errors=True)
        return deleted

    def _upload_s3(self, key: str, content: bytes, content_type: str) -> str:
        self._client.put_object(
            Bucket=settings.storage_bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            CacheControl="public, max-age=3600",
        )
        if settings.storage_public_url:
            base = settings.storage_public_url.rstrip("/")
            return f"{base}/{key}"
        return f"{settings.storage_endpoint}/{settings.storage_bucket}/{key}"

    def _upload_local(self, key: str, content: bytes, content_type: str) -> str:
        path = self._local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return f"/static/previews/{key}"

    @staticmethod
    def _local_path(key: str) -> Path:
        base = Path(__file__).resolve().parent.parent.parent / "static" / "previews"
        resolved = (base / key).resolve()
        if not resolved.is_relative_to(base):
            raise ValueError("Invalid storage key: path traversal detected")
        return resolved


_adapter: StorageAdapter | None = None


def get_storage() -> StorageAdapter:
    global _adapter
    if _adapter is None:
        _adapter = StorageAdapter()
    return _adapter
