"""Adaptador real de reconhecimento de imagem via Amazon Rekognition Image.

Uso do `boto3` encapsulado neste adaptador - o dominio
(`app.processors.image`) so ve `ImageRecognitionAdapter` (Protocol).
Diferente do Transcribe (job assincrono, batch), `DetectLabels` e
SINCRONO e aceita uma referencia direta ao objeto no S3
(`Image={"S3Object": {"Bucket": ..., "Name": ...}}`) - nao ha polling nem
bucket de saida separado.

`request.storage_key` e a chave "nua" gravada no banco (sem prefixo de
area); o objeto so existe em `s3://{bucket}/approved/...` depois de
`S3StorageAdapter.promote()` (app/storage/s3.py) - usa `APPROVED_PREFIX`
para nao duplicar a string literal, mesmo padrao do `AwsTranscribeAdapter`.

**Nao exercitado contra a API real da AWS neste ambiente** (sem
credenciais/rede) - testado com um cliente `boto3` falso injetado
(`tests/test_image_recognition_adapters.py`), verificando construcao da
requisicao e parsing da resposta.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.core.enums import VisionAnalysisStatus
from app.integrations.image_recognition.base import (
    ImageLabelFinding,
    ImageRecognitionRequest,
    ImageRecognitionResult,
)
from app.storage.s3 import APPROVED_PREFIX

logger = logging.getLogger(__name__)


class _RekognitionClient(Protocol):
    def detect_labels(self, **kwargs: Any) -> dict: ...


class AwsRekognitionImageAdapter:
    def __init__(
        self,
        *,
        rekognition_client: _RekognitionClient,
        media_bucket: str,
        max_labels: int = 20,
    ) -> None:
        self._rekognition = rekognition_client
        self._media_bucket = media_bucket
        self._max_labels = max_labels

    def detect_labels(self, request: ImageRecognitionRequest) -> ImageRecognitionResult:
        object_key = APPROVED_PREFIX + request.storage_key

        logger.info(
            "Chamando Rekognition DetectLabels bucket=%s key=%s max_labels=%s min_confidence=%s",
            self._media_bucket,
            object_key,
            self._max_labels,
            request.min_confidence,
        )

        try:
            response = self._rekognition.detect_labels(
                Image={"S3Object": {"Bucket": self._media_bucket, "Name": object_key}},
                MaxLabels=self._max_labels,
                MinConfidence=request.min_confidence,
            )
        except Exception as exc:  # noqa: BLE001 - erro de fornecedor nunca propaga cru
            logger.warning("Falha ao chamar Rekognition DetectLabels: %s", exc)
            return self._failed_result(f"Falha ao chamar DetectLabels: {exc}")

        # Log da resposta CRUA do Rekognition (apenas rotulos/metadados
        # genericos devolvidos pelo servico - nunca os bytes da imagem, nem
        # dado clinico identificado - logs nao podem conter conteudo
        # clinico/PII, e esta resposta e so uma lista de rotulos genericos
        # como "Person"/"X-Ray" com a confianca reportada).
        logger.info("Resposta do Rekognition DetectLabels: %s", response)

        try:
            labels = [
                ImageLabelFinding(
                    label=str(item["Name"]), confidence=float(item["Confidence"])
                )
                for item in response.get("Labels", [])
            ]
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Falha ao interpretar resposta do Rekognition: %s", exc)
            return self._failed_result(f"Falha ao interpretar resposta do Rekognition: {exc}")

        return ImageRecognitionResult(
            status=VisionAnalysisStatus.COMPLETED,
            provider="aws_rekognition",
            labels=labels,
        )

    def _failed_result(self, error: str) -> ImageRecognitionResult:
        return ImageRecognitionResult(
            status=VisionAnalysisStatus.FAILED,
            provider="aws_rekognition",
            labels=[],
            error=error[:500],
        )
