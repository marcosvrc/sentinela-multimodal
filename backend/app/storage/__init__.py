"""Selecao do adaptador de armazenamento de midia por configuracao."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.enums import StorageBackend
from app.storage.base import StorageAdapter
from app.storage.local import LocalFilesystemStorageAdapter


@lru_cache
def get_storage_adapter() -> StorageAdapter:
    settings = get_settings()

    if settings.media_storage_backend is StorageBackend.LOCAL:
        return LocalFilesystemStorageAdapter(
            storage_root=settings.media_local_storage_root,
            upload_secret=settings.media_local_upload_secret,
            upload_url_ttl_seconds=settings.media_upload_url_ttl_seconds,
        )

    if settings.media_storage_backend is StorageBackend.S3:
        if not settings.s3_media_bucket:
            raise RuntimeError("media_storage_backend=S3 exige S3_MEDIA_BUCKET configurado.")
        from app.storage.s3 import S3StorageAdapter

        return S3StorageAdapter(
            bucket=settings.s3_media_bucket,
            region=settings.aws_region,
            upload_url_ttl_seconds=settings.media_upload_url_ttl_seconds,
        )

    raise RuntimeError(f"Backend de armazenamento desconhecido: {settings.media_storage_backend}")
