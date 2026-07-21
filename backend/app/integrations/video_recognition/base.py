"""Contrato do adaptador de reconhecimento de video (Amazon Rekognition
Video) - fonte COMPLEMENTAR de deteccao de objetos em video.

Mesmo padrao arquitetural dos demais adaptadores. `VideoRecognitionRequest`
carrega apenas a referencia ao objeto ja aprovado no S3 (nunca bytes
inline) - diferente do adaptador de visao self-hosted
(`app.integrations.vision`, que recebe os bytes porque o worker local
mesmo os decodifica), o Rekognition Video roda do outro lado da rede,
mesmo principio de minimizacao do `AwsTranscribeAdapter`.

Este adaptador NUNCA substitui o worker self-hosted OpenPose/YOLOv8
(`app.integrations.vision`) - o Rekognition nao oferece estimativa de
pose articulada, que e requisito central desta modalidade de video. Ele
adiciona apenas rotulos genericos com timestamp (ex.: "Person", "Bed")
como achado complementar, sempre apresentado em separado do achado de
pose/deteccao do worker self-hosted."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.enums import VisionAnalysisStatus


@dataclass(frozen=True)
class VideoRecognitionRequest:
    """Referencia ao objeto de video ja aprovado (nunca os bytes inline)."""

    storage_key: str
    job_name: str
    min_confidence: float = 55.0


@dataclass(frozen=True)
class VideoLabelFinding:
    """Um rotulo generico devolvido pelo Rekognition Video, com o
    timestamp (em milissegundos desde o inicio do video) em que foi
    detectado - preserva a correlacao temporal, guardando o timestamp
    inicial/final de cada deteccao."""

    label: str
    confidence: float
    timestamp_millis: int


@dataclass(frozen=True)
class VideoRecognitionResult:
    status: VisionAnalysisStatus
    provider: str
    job_name: str
    labels: list[VideoLabelFinding] = field(default_factory=list)
    error: str | None = None


class VideoRecognitionAdapter(Protocol):
    """Implementado por `LocalUnavailableVideoRecognitionAdapter` (dev/
    testes) e `AwsRekognitionVideoAdapter` (real)."""

    def detect_labels(self, request: VideoRecognitionRequest) -> VideoRecognitionResult: ...
