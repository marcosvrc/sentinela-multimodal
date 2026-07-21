"""Adaptador real de reconhecimento de video via Amazon Rekognition Video.

Uso do `boto3` encapsulado neste adaptador - o dominio
(`app.processors.video`) so ve `VideoRecognitionAdapter` (Protocol). Segue
o mesmo padrao assincrono do `AwsTranscribeAdapter`: job por referencia ao
S3, poll sincrono ate concluir, sem bucket de saida (a
resposta com os rotulos vem diretamente de `GetLabelDetection`, nao de um
arquivo gravado pelo servico).

1. `start_label_detection` apontando para o objeto ja aprovado no bucket
   de midia (`s3://{media_bucket}/approved/{storage_key}` - reaproveita
   `APPROVED_PREFIX`, mesma fonte unica de verdade usada pelo Transcribe e
   pelo Rekognition Image).
2. Poll de `get_label_detection` ate `SUCCEEDED`/`FAILED`, com numero
   maximo de tentativas e intervalo fixo (mesma limitacao MVP documentada
   no Transcribe - poll sincrono dentro do worker, adequado para videos
   curtos de demonstracao).
3. Extracao dos rotulos com o timestamp em que cada um foi observado
   (`Timestamp`, milissegundos desde o inicio) - preserva a correlacao
   temporal, guardando timestamp inicial/final de cada deteccao.

**Nao exercitado contra a API real da AWS neste ambiente** (sem
credenciais/rede) - testado com um cliente `boto3` falso injetado
(`tests/test_video_recognition_adapters.py`).
"""

from __future__ import annotations

import time
from typing import Any, Protocol

from app.core.enums import VisionAnalysisStatus
from app.integrations.video_recognition.base import (
    VideoLabelFinding,
    VideoRecognitionRequest,
    VideoRecognitionResult,
)
from app.storage.s3 import APPROVED_PREFIX


class _RekognitionVideoClient(Protocol):
    def start_label_detection(self, **kwargs: Any) -> dict: ...
    def get_label_detection(self, **kwargs: Any) -> dict: ...


class AwsRekognitionVideoAdapter:
    def __init__(
        self,
        *,
        rekognition_client: _RekognitionVideoClient,
        media_bucket: str,
        poll_interval_seconds: float = 5.0,
        max_poll_attempts: int = 60,
        max_labels: int = 50,
    ) -> None:
        self._rekognition = rekognition_client
        self._media_bucket = media_bucket
        self._poll_interval_seconds = poll_interval_seconds
        self._max_poll_attempts = max_poll_attempts
        self._max_labels = max_labels

    def detect_labels(self, request: VideoRecognitionRequest) -> VideoRecognitionResult:
        object_key = APPROVED_PREFIX + request.storage_key

        try:
            start_response = self._rekognition.start_label_detection(
                Video={"S3Object": {"Bucket": self._media_bucket, "Name": object_key}},
                MinConfidence=request.min_confidence,
            )
            job_id = start_response["JobId"]
        except Exception as exc:  # noqa: BLE001 - erro de fornecedor nunca propaga cru
            return self._failed_result(request, f"Falha ao iniciar job: {exc}")

        job_status = None
        response: dict = {}
        for _ in range(self._max_poll_attempts):
            try:
                response = self._rekognition.get_label_detection(
                    JobId=job_id, SortBy="TIMESTAMP", MaxResults=self._max_labels
                )
            except Exception as exc:  # noqa: BLE001
                return self._failed_result(request, f"Falha ao consultar job: {exc}")

            job_status = response.get("JobStatus")
            if job_status in ("SUCCEEDED", "FAILED"):
                break
            time.sleep(self._poll_interval_seconds)

        if job_status != "SUCCEEDED":
            reason = "timeout aguardando conclusao" if job_status is None else job_status
            return self._failed_result(request, f"Job de reconhecimento nao concluido: {reason}")

        try:
            labels = [
                VideoLabelFinding(
                    label=str(item["Label"]["Name"]),
                    confidence=float(item["Label"]["Confidence"]),
                    timestamp_millis=int(item["Timestamp"]),
                )
                for item in response.get("Labels", [])
            ]
        except (KeyError, TypeError, ValueError) as exc:
            return self._failed_result(request, f"Falha ao interpretar resposta do Rekognition: {exc}")

        return VideoRecognitionResult(
            status=VisionAnalysisStatus.COMPLETED,
            provider="aws_rekognition_video",
            job_name=request.job_name,
            labels=labels,
        )

    def _failed_result(
        self, request: VideoRecognitionRequest, error: str
    ) -> VideoRecognitionResult:
        return VideoRecognitionResult(
            status=VisionAnalysisStatus.FAILED,
            provider="aws_rekognition_video",
            job_name=request.job_name,
            labels=[],
            error=error[:500],
        )
