"""Testes do adaptador de storage local (filesystem), sem banco de dados."""

from __future__ import annotations

import hashlib
import time

import pytest

from app.storage.local import (
    LocalFilesystemStorageAdapter,
    LocalUploadTokenError,
    decode_local_upload_token,
    encode_local_upload_token,
)

SECRET = "test-secret"


@pytest.fixture
def adapter(tmp_path) -> LocalFilesystemStorageAdapter:
    return LocalFilesystemStorageAdapter(
        storage_root=str(tmp_path), upload_secret=SECRET, upload_url_ttl_seconds=900
    )


def test_encode_decode_token_roundtrip() -> None:
    token = encode_local_upload_token(quarantine_key="a/b/c", ttl_seconds=60, secret=SECRET)
    decoded = decode_local_upload_token(token, secret=SECRET)
    assert decoded.quarantine_key == "a/b/c"


def test_decode_token_rejects_wrong_secret() -> None:
    token = encode_local_upload_token(quarantine_key="a/b/c", ttl_seconds=60, secret=SECRET)
    with pytest.raises(LocalUploadTokenError):
        decode_local_upload_token(token, secret="wrong-secret")


def test_decode_token_rejects_expired_token() -> None:
    token = encode_local_upload_token(quarantine_key="a/b/c", ttl_seconds=-1, secret=SECRET)
    with pytest.raises(LocalUploadTokenError):
        decode_local_upload_token(token, secret=SECRET)


def test_decode_token_rejects_malformed_token() -> None:
    with pytest.raises(LocalUploadTokenError):
        decode_local_upload_token("not-a-valid-token", secret=SECRET)


def test_create_presigned_upload_returns_local_endpoint(
    adapter: LocalFilesystemStorageAdapter,
) -> None:
    presigned = adapter.create_presigned_upload(
        quarantine_key="inst/analysis/media", declared_mime_type="image/png", declared_size_bytes=10
    )
    assert presigned.method == "PUT"
    assert presigned.url.startswith("/media/local-storage/")
    assert presigned.headers["Content-Type"] == "image/png"


def test_write_and_stat_quarantined_object(adapter: LocalFilesystemStorageAdapter) -> None:
    content = b"hello world"
    adapter.write_quarantined_object("key1", content)

    metadata = adapter.stat_quarantined_object("key1")
    assert metadata is not None
    assert metadata.size_bytes == len(content)
    assert metadata.checksum_sha256 == hashlib.sha256(content).hexdigest()
    assert metadata.content_prefix == content


def test_stat_quarantined_object_returns_none_when_missing(
    adapter: LocalFilesystemStorageAdapter,
) -> None:
    assert adapter.stat_quarantined_object("does-not-exist") is None


def test_promote_moves_object_from_quarantine_to_approved(
    adapter: LocalFilesystemStorageAdapter,
) -> None:
    adapter.write_quarantined_object("key2", b"content")
    adapter.promote(quarantine_key="key2", approved_key="key2")

    assert adapter.stat_quarantined_object("key2") is None
    assert (adapter._approved_path("key2")).read_bytes() == b"content"  # noqa: SLF001


def test_delete_quarantined_object_removes_file(adapter: LocalFilesystemStorageAdapter) -> None:
    adapter.write_quarantined_object("key3", b"content")
    adapter.delete_quarantined_object("key3")
    assert adapter.stat_quarantined_object("key3") is None


def test_delete_quarantined_object_is_idempotent(adapter: LocalFilesystemStorageAdapter) -> None:
    # Nao deve lancar excecao mesmo se o objeto ja nao existir (rejeicao
    # dupla, expiracao apos rejeicao, etc.).
    adapter.delete_quarantined_object("never-existed")


def test_expires_at_reflects_ttl(adapter: LocalFilesystemStorageAdapter) -> None:
    before = time.time()
    presigned = adapter.create_presigned_upload(
        quarantine_key="k", declared_mime_type="image/png", declared_size_bytes=1
    )
    assert presigned.expires_at.timestamp() > before
