"""Adaptador de armazenamento em filesystem local (dev/testes).

TEMPORARIO: destinado apenas a desenvolvimento/testes. Diferente do S3
real, aqui a "URL pre-assinada" aponta para um endpoint da propria API
(`PUT /media/local-storage/{token}`, ver app/api/routes/media.py) - o
arquivo passa pelo processo da API neste adaptador, o que NAO reproduz a
propriedade "o backend nunca recebe o arquivo como intermediario" que a
transferencia direta frontend-storage exige. Isso e uma limitacao
aceita do adaptador local, documentada aqui; o adaptador
`S3StorageAdapter` (app/storage/s3.py) e quem implementa a transferencia
direta frontend-armazenamento exigida em producao.

O token de upload e assinado (HMAC-SHA256) com `media_local_upload_secret`
e carrega a chave do objeto e a expiracao, para que o endpoint de upload
nao precise consultar o banco para validar a URL.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.storage.base import ObjectMetadata, PresignedUpload

_SNIFF_PREFIX_BYTES = 128


@dataclass(frozen=True)
class LocalUploadToken:
    quarantine_key: str
    expires_at_epoch: int


class LocalUploadTokenError(Exception):
    """Token de upload local ausente, invalido, adulterado ou expirado."""


def _sign(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def encode_local_upload_token(*, quarantine_key: str, ttl_seconds: int, secret: str) -> str:
    expires_at_epoch = int(time.time()) + ttl_seconds
    payload = json.dumps(
        {"quarantine_key": quarantine_key, "expires_at": expires_at_epoch}, sort_keys=True
    ).encode("utf-8")
    signature = _sign(payload, secret)
    token_bytes = payload + b"." + signature.encode("utf-8")
    return base64.urlsafe_b64encode(token_bytes).decode("ascii")


def decode_local_upload_token(token: str, *, secret: str) -> LocalUploadToken:
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        payload, _, signature = raw.rpartition(b".")
    except Exception as exc:  # noqa: BLE001
        raise LocalUploadTokenError("Token de upload malformado.") from exc

    if not payload or not signature:
        raise LocalUploadTokenError("Token de upload malformado.")

    expected_signature = _sign(payload, secret)
    if not hmac.compare_digest(expected_signature, signature.decode("ascii")):
        raise LocalUploadTokenError("Assinatura do token de upload invalida.")

    data = json.loads(payload)
    expires_at_epoch = int(data["expires_at"])
    if time.time() > expires_at_epoch:
        raise LocalUploadTokenError("Token de upload expirado.")

    return LocalUploadToken(
        quarantine_key=data["quarantine_key"], expires_at_epoch=expires_at_epoch
    )


class LocalFilesystemStorageAdapter:
    """Implementa `StorageAdapter` gravando arquivos sob `storage_root`."""

    def __init__(self, *, storage_root: str, upload_secret: str, upload_url_ttl_seconds: int):
        self._root = Path(storage_root)
        self._upload_secret = upload_secret
        self._upload_url_ttl_seconds = upload_url_ttl_seconds
        (self._root / "quarantine").mkdir(parents=True, exist_ok=True)
        (self._root / "approved").mkdir(parents=True, exist_ok=True)
        (self._root / "generated").mkdir(parents=True, exist_ok=True)

    def _quarantine_path(self, key: str) -> Path:
        return self._root / "quarantine" / key

    def _approved_path(self, key: str) -> Path:
        return self._root / "approved" / key

    def _generated_path(self, key: str) -> Path:
        return self._root / "generated" / key

    def create_presigned_upload(
        self, *, quarantine_key: str, declared_mime_type: str, declared_size_bytes: int
    ) -> PresignedUpload:
        token = encode_local_upload_token(
            quarantine_key=quarantine_key,
            ttl_seconds=self._upload_url_ttl_seconds,
            secret=self._upload_secret,
        )
        expires_at = datetime.fromtimestamp(
            time.time() + self._upload_url_ttl_seconds, tz=timezone.utc
        )
        return PresignedUpload(
            storage_key=quarantine_key,
            url=f"/media/local-storage/{token}",
            method="PUT",
            headers={"Content-Type": declared_mime_type},
            expires_at=expires_at,
        )

    def write_quarantined_object(self, quarantine_key: str, content: bytes) -> None:
        """Usado apenas pelo endpoint local de upload (nao faz parte de `StorageAdapter`)."""
        path = self._quarantine_path(quarantine_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def stat_quarantined_object(self, quarantine_key: str) -> ObjectMetadata | None:
        path = self._quarantine_path(quarantine_key)
        if not path.is_file():
            return None
        content = path.read_bytes()
        return ObjectMetadata(
            size_bytes=len(content),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            content_prefix=content[:_SNIFF_PREFIX_BYTES],
        )

    def promote(self, *, quarantine_key: str, approved_key: str) -> None:
        source = self._quarantine_path(quarantine_key)
        destination = self._approved_path(approved_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)

    def delete_quarantined_object(self, quarantine_key: str) -> None:
        path = self._quarantine_path(quarantine_key)
        path.unlink(missing_ok=True)

    def read_approved_object(self, approved_key: str) -> bytes:
        return self._approved_path(approved_key).read_bytes()

    def write_generated_object(
        self, *, generated_key: str, content: bytes, content_type: str
    ) -> None:
        path = self._generated_path(generated_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read_generated_object(self, generated_key: str) -> bytes:
        return self._generated_path(generated_key).read_bytes()
