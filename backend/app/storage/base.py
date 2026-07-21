"""Interface de armazenamento de midia.

Duas implementacoes: `LocalFilesystemStorageAdapter` (dev/testes) e
`S3StorageAdapter` (homologacao/producao). Nenhum outro modulo deve falar
diretamente com `boto3` ou o filesystem para midia - sempre por esta
interface, selecionada por `app.storage.get_storage_adapter()` a partir de
`Settings.media_storage_backend`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class PresignedUpload:
    """Instrucoes para o frontend enviar o arquivo diretamente ao storage.

    `url`/`method`/`headers` sao repassados ao frontend tal qual; a API
    nunca recebe o arquivo como intermediario (upload vai direto do
    navegador para o storage). Nada aqui e persistido em log ou auditoria
    (apenas a chave do objeto e o resultado da confirmacao).
    """

    storage_key: str
    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class ObjectMetadata:
    """Metadados observados de um objeto ja enviado ao storage."""

    size_bytes: int
    checksum_sha256: str
    content_prefix: bytes  # primeiros bytes, para sniff de assinatura de arquivo


class StorageAdapter(Protocol):
    """Contrato que qualquer backend de midia deve cumprir."""

    def create_presigned_upload(
        self, *, quarantine_key: str, declared_mime_type: str, declared_size_bytes: int
    ) -> PresignedUpload: ...

    def stat_quarantined_object(self, quarantine_key: str) -> ObjectMetadata | None:
        """Le metadados do objeto na area de quarentena, ou `None` se ausente."""
        ...

    def promote(self, *, quarantine_key: str, approved_key: str) -> None:
        """Move o objeto de quarentena para a area aprovada (irreversivel)."""
        ...

    def delete_quarantined_object(self, quarantine_key: str) -> None:
        """Remove um objeto reprovado/expirado da quarentena."""
        ...

    def read_approved_object(self, approved_key: str) -> bytes:
        """Le o conteudo integral de um objeto ja promovido (usado pelos processadores
        de modalidade para ler o arquivo aprovado e produzir achados)."""
        ...

    def write_generated_object(
        self, *, generated_key: str, content: bytes, content_type: str
    ) -> None:
        """Grava um artefato gerado pelo proprio backend (ex.: PDF de
        relatorio). Diferente da area de quarentena/aprovada (que segue o
        fluxo de upload do cliente com `promote`/`delete_quarantined_object`),
        esta area e escrita diretamente pelo servidor - sem sinalizacao,
        varredura antimalware ou verificacao de assinatura, porque o
        conteudo nao veio de um cliente nao confiavel."""
        ...

    def read_generated_object(self, generated_key: str) -> bytes:
        """Le um artefato gerado pelo backend (ver `write_generated_object`)."""
        ...
