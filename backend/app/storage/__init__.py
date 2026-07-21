"""Selecao do adaptador de armazenamento de midia por configuracao."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import StorageAdapter
from app.storage.local import LocalFilesystemStorageAdapter


@lru_cache
def get_storage_adapter() -> StorageAdapter:
    settings = get_settings()

    return LocalFilesystemStorageAdapter(
        storage_root=settings.media_local_storage_root,
        upload_secret=settings.media_local_upload_secret,
        upload_url_ttl_seconds=settings.media_upload_url_ttl_seconds,
    )
