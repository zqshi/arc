"""S3-compatible object storage adapter with local filesystem fallback.

Supports:
- Single file upload (upload / async_upload)
- Directory upload (upload_dir / async_upload_dir) — recursive, preserves structure
- Prefix deletion (delete_prefix / async_delete_prefix)
- Configurable max file size (default 50MB for deploy, 2MB for preview)
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
from pathlib import Path

from arc.config import settings

logger = logging.getLogger(__name__)

# Default limits — callers can override via max_size param
DEFAULT_MAX_UPLOAD_SIZE = 2 * 1024 * 1024  # 2 MB (preview compat)
DEPLOY_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB (deployment)
MULTIPART_THRESHOLD = 10 * 1024 * 1024  # 10 MB — above this, use multipart

# Backwards-compat alias
MAX_UPLOAD_SIZE = DEFAULT_MAX_UPLOAD_SIZE


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
        *, max_size: int = DEFAULT_MAX_UPLOAD_SIZE,
    ) -> str:
        if len(content) > max_size:
            raise ValueError(f"Upload exceeds {max_size} bytes limit ({len(content)} bytes)")
        if self._is_s3:
            return self._upload_s3(key, content, content_type)
        return self._upload_local(key, content, content_type)

    async def async_upload(
        self, key: str, content: bytes, content_type: str = "text/html",
        *, max_size: int = DEFAULT_MAX_UPLOAD_SIZE,
    ) -> str:
        return await asyncio.to_thread(self.upload, key, content, content_type, max_size=max_size)

    def upload_dir(self, local_dir: str, prefix: str, *, max_file_size: int = DEPLOY_MAX_UPLOAD_SIZE) -> int:
        """递归上传目录到 S3 prefix，保持相对路径结构。

        Args:
            local_dir: 本地目录路径
            prefix: S3 key 前缀（如 deployments/proj_id/deploy_id）
            max_file_size: 单文件大小上限（默认 50MB）

        Returns:
            上传文件数量

        Raises:
            ValueError: 目录不存在或单文件超限
        """
        base = Path(local_dir)
        if not base.is_dir():
            raise ValueError(f"目录不存在: {local_dir}")

        uploaded = 0
        for file_path in base.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(base)
            key = f"{prefix}/{rel.as_posix()}"
            content = file_path.read_bytes()
            if len(content) > max_file_size:
                raise ValueError(
                    f"文件 {rel} 超过大小限制: {len(content)} > {max_file_size}"
                )
            content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            if self._is_s3:
                self._upload_s3(key, content, content_type)
            else:
                self._upload_local(key, content, content_type)
            uploaded += 1

        logger.info("upload_dir: %s → %s (%d files)", local_dir, prefix, uploaded)
        return uploaded

    async def async_upload_dir(
        self, local_dir: str, prefix: str, *, max_file_size: int = DEPLOY_MAX_UPLOAD_SIZE
    ) -> int:
        """异步版 upload_dir。"""
        return await asyncio.to_thread(self.upload_dir, local_dir, prefix, max_file_size=max_file_size)

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


def get_public_url(key: str) -> str:
    """Construct public URL for a storage key."""
    if settings.storage_public_url:
        return f"{settings.storage_public_url.rstrip('/')}/{key}"
    if settings.storage_endpoint:
        return f"{settings.storage_endpoint}/{settings.storage_bucket}/{key}"
    return f"/static/previews/{key}"
