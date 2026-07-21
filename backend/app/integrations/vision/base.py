"""Contrato do adaptador de visao computacional de video.

Mesmo padrao arquitetural dos demais adaptadores (`app.integrations.llm`,
`app.integrations.transcription`): o dominio (`app.processors.video`)
depende apenas deste `Protocol`, nunca de bibliotecas de visao
computacional diretamente. `VideoAnalysisRequest` carrega apenas a
referencia ao objeto de video ja aprovado (nunca os bytes inline em log ou
mensagem de fila), mesmo principio de minimizacao usado no LLM e na
transcricao.

Ao contrario do adaptador de transcricao (que chama um servico AWS via
`boto3`), o adaptador real desta modalidade e um worker self-hosted
(OpenPose + YOLOv8 em CPU) - decisao tomada apos avaliar o Amazon
Rekognition, que nao oferece estimativa de pose. Por isso o `Protocol` de
mais baixo nivel (`PoseEngine`,
`DetectionEngine`, `FrameExtractor`) tambem fica aqui, permitindo testar a
orquestracao do adaptador real com engines falsas injetadas - mesmo padrao
de injecao de dependencia usado no cliente `boto3` falso do
`AwsTranscribeAdapter`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.enums import VisionAnalysisStatus


@dataclass(frozen=True)
class VideoAnalysisRequest:
    """Diferente de `TranscriptionRequest` (que so leva a referencia no S3,
    porque quem le o objeto e o servico AWS do outro lado da rede), aqui o
    proprio worker de video e quem extrai os quadros - o processador
    (`app.processors.video`) ja leu o objeto aprovado do storage para
    calcular a duracao estrutural, entao os bytes sao passados diretamente
    (chamada dentro do mesmo processo, nao uma mensagem de fila nem uma
    requisicao de rede - o principio de minimizacao aqui se aplica a nunca
    enviar os bytes a um terceiro, nao a evitar passa-los localmente)."""

    storage_key: str
    media_format: str  # "mp4" | "mov"
    max_sample_frames: int
    video_bytes: bytes


@dataclass(frozen=True)
class PoseFrameFinding:
    """Resultado de estimativa de pose (OpenPose) em um quadro amostrado.

    `person_count`/`mean_keypoint_confidence` sao agregados reais devolvidos
    pelo motor de pose - nunca uma inferencia clinica. Interpretacao
    clinica (ex.: "padrao postural anomalo") so pode ser feita por um
    profissional a partir da evidencia (indice do quadro), nunca pelo
    adaptador."""

    frame_index: int
    person_count: int
    mean_keypoint_confidence: float | None
    model_version: str


@dataclass(frozen=True)
class DetectionFrameFinding:
    """Resultado de deteccao de objetos (YOLOv8) em um quadro amostrado."""

    frame_index: int
    label: str
    confidence: float
    model_version: str


@dataclass(frozen=True)
class VideoAnalysisResult:
    """`pose_enabled`/`detection_enabled` distinguem "motor desligado por
    feature flag" (`vision_pose_enabled=false`/`vision_detection_enabled=
    false`, tela `/admin/feature-flags` - considerar YOLOv8 e OpenPose
    separadamente) de "motor rodou e nao achou nada" (`pose_findings`/
    `detection_findings`
    vazios com o motor habilitado) - `app.processors.video` usa essa
    distincao para nunca resumir "0 pessoas detectadas" quando o motor de
    pose simplesmente nao rodou."""

    status: VisionAnalysisStatus
    provider: str
    frames_analyzed: int
    pose_enabled: bool = True
    detection_enabled: bool = True
    pose_findings: list[PoseFrameFinding] = field(default_factory=list)
    detection_findings: list[DetectionFrameFinding] = field(default_factory=list)
    error: str | None = None


class VideoAnalysisAdapter(Protocol):
    """Implementado por `LocalUnavailableVisionAdapter` (dev/testes) e
    `OpenPoseYoloVideoAdapter` (real, worker self-hosted)."""

    def analyze(self, request: VideoAnalysisRequest) -> VideoAnalysisResult: ...


class FrameExtractor(Protocol):
    """Extrai quadros amostrados do video para JPEG, sem decodificar o
    arquivo inteiro. Implementacao real usa `ffmpeg` instalado no container
    do worker; nao ha decodificador H.264 puro-Python neste projeto -
    isolar essa extracao aqui evita que o dominio dependa de um binario
    externo."""

    def extract_sample_frames(self, video_bytes: bytes, *, max_frames: int) -> list[bytes]: ...


class PoseEngine(Protocol):
    """Estimativa de pose (OpenPose) sobre um quadro JPEG isolado."""

    def estimate(self, frame_jpeg: bytes) -> list[dict]: ...


class DetectionEngine(Protocol):
    """Deteccao de objetos (YOLOv8) sobre um quadro JPEG isolado."""

    def detect(self, frame_jpeg: bytes) -> list[dict]: ...
