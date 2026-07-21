"""Adaptador de armazenamento em Amazon S3 (homologacao/producao).

Implementa a transferencia direta frontend-S3: a API apenas gera a URL
pre-assinada com `boto3` (credenciais do IAM Role do processo, nunca
fixas no codigo); o navegador executa o `PUT` diretamente contra o S3.

Nao exercitado pelos testes deste sandbox (sem credenciais/conta AWS); os
testes de integracao reais rodam separadamente contra uma conta AWS de
desenvolvimento quando credenciais estiverem disponiveis.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config

from app.storage.base import ObjectMetadata, PresignedUpload

_QUARANTINE_PREFIX = "quarantine/"
# Publico (sem "_") porque `AwsTranscribeAdapter` (app/integrations/
# transcription/aws_transcribe.py) precisa montar a URI `s3://bucket/key`
# do MESMO objeto aprovado que este adapter gerencia, sem duplicar a
# string literal do prefixo em dois modulos (fonte unica de verdade).
APPROVED_PREFIX = "approved/"
_GENERATED_PREFIX = "generated/"
_SNIFF_PREFIX_BYTES = 128


class S3StorageAdapter:
    def __init__(self, *, bucket: str, region: str, upload_url_ttl_seconds: int):
        self._bucket = bucket
        self._ttl_seconds = upload_url_ttl_seconds
        # SigV4 explicito: o bucket usa SSE-KMS por padrao (infra/modules/
        # storage), que EXIGE assinatura V4 nas URLs pre-assinadas - sem
        # isso, boto3 pode assinar com SigV2 em us-east-1 (regiao legada
        # que ainda aceita os dois esquemas para a maioria das operacoes),
        # e o S3 rejeita o upload com "Requests specifying Server Side
        # Encryption with AWS KMS managed keys require AWS Signature
        # Version 4".
        self._client = boto3.client(
            "s3", region_name=region, config=Config(signature_version="s3v4")
        )

    def create_presigned_upload(
        self, *, quarantine_key: str, declared_mime_type: str, declared_size_bytes: int
    ) -> PresignedUpload:
        object_key = _QUARANTINE_PREFIX + quarantine_key
        url = self._client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": self._bucket,
                "Key": object_key,
                "ContentType": declared_mime_type,
                # Impede sobrescrita silenciosa de objeto ja promovido/em uso:
                # URLs pre-assinadas nao podem sobrescrever objetos existentes.
                "IfNoneMatch": "*",
            },
            ExpiresIn=self._ttl_seconds,
        )
        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=self._ttl_seconds)
        return PresignedUpload(
            storage_key=quarantine_key,
            url=url,
            method="PUT",
            # `If-None-Match` PRECISA ir aqui tambem, nao so em `Params`
            # acima: uma URL pre-assinada SigV4 inclui esse cabecalho na
            # lista de assinados (`X-Amz-SignedHeaders`), entao o cliente
            # tem que envia-lo com o MESMO valor no PUT real - sem isso o
            # S3 rejeita com 403 "SignatureDoesNotMatch" (o upload nunca
            # chega a ser tentado com um header divergente, e sim com o
            # header simplesmente ausente).
            headers={"Content-Type": declared_mime_type, "If-None-Match": "*"},
            expires_at=expires_at,
        )

    def stat_quarantined_object(self, quarantine_key: str) -> ObjectMetadata | None:
        object_key = _QUARANTINE_PREFIX + quarantine_key
        try:
            head = self._client.head_object(Bucket=self._bucket, Key=object_key)
        except self._client.exceptions.ClientError:
            return None

        body = self._client.get_object(
            Bucket=self._bucket, Key=object_key, Range=f"bytes=0-{_SNIFF_PREFIX_BYTES - 1}"
        )["Body"].read()
        full_object = self._client.get_object(Bucket=self._bucket, Key=object_key)["Body"].read()
        return ObjectMetadata(
            size_bytes=head["ContentLength"],
            checksum_sha256=hashlib.sha256(full_object).hexdigest(),
            content_prefix=body,
        )

    def promote(self, *, quarantine_key: str, approved_key: str) -> None:
        source_key = _QUARANTINE_PREFIX + quarantine_key
        destination_key = APPROVED_PREFIX + approved_key
        self._client.copy_object(
            Bucket=self._bucket,
            CopySource={"Bucket": self._bucket, "Key": source_key},
            Key=destination_key,
        )
        self._client.delete_object(Bucket=self._bucket, Key=source_key)

    def delete_quarantined_object(self, quarantine_key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=_QUARANTINE_PREFIX + quarantine_key)

    def read_approved_object(self, approved_key: str) -> bytes:
        object_key = APPROVED_PREFIX + approved_key
        return self._client.get_object(Bucket=self._bucket, Key=object_key)["Body"].read()

    def write_generated_object(
        self, *, generated_key: str, content: bytes, content_type: str
    ) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=_GENERATED_PREFIX + generated_key,
            Body=content,
            ContentType=content_type,
        )

    def read_generated_object(self, generated_key: str) -> bytes:
        object_key = _GENERATED_PREFIX + generated_key
        return self._client.get_object(Bucket=self._bucket, Key=object_key)["Body"].read()
