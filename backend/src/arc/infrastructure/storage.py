"""S3-compatible object storage adapter with local filesystem fallback."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from arc.config import settings

logger = logging.getLogger(__name__)


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

    def upload(self, key: str, content: bytes, content_type: str = "text/html") -> str:
        if self._is_s3:
            return self._upload_s3(key, content, content_type)
        return self._upload_local(key, content, content_type)

    def delete(self, key: str) -> None:
        if self._is_s3:
            self._client.delete_object(Bucket=settings.storage_bucket, Key=key)
        else:
            path = self._local_path(key)
            if path.exists():
                path.unlink()

    def _upload_s3(self, key: str, content: bytes, content_type: str) -> str:
        self._client.put_object(
            Bucket=settings.storage_bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
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
        return base / key


_adapter: StorageAdapter | None = None


def get_storage() -> StorageAdapter:
    global _adapter
    if _adapter is None:
        _adapter = StorageAdapter()
    return _adapter
