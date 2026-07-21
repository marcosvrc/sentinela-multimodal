"""Adaptador LOCAL de visao computacional: honesto sobre nao ter motor de
pose/deteccao.

TEMPORARIO (mesmo padrao dos demais adaptadores locais - storage, fila,
identidade, LLM, transcricao). Diferente do adaptador LOCAL de LLM (que
produz um resumo deterministico real via template), este NAO pode produzir
achados de pose ou objetos reais - isso exige OpenPose/YOLOv8 (ou
equivalente) rodando de fato, que este ambiente nao tem. Retornar
keypoints ou deteccoes fabricadas seria pior que nao analisar (viola o
principio "nunca fingir" usado em todo o projeto). Por isso este adaptador
sempre retorna `VisionAnalysisStatus.UNAVAILABLE`, nunca `COMPLETED`, e com
listas de achados vazias.
"""

from __future__ import annotations

from app.core.enums import VisionAnalysisStatus
from app.integrations.vision.base import VideoAnalysisRequest, VideoAnalysisResult


class LocalUnavailableVisionAdapter:
    def analyze(self, request: VideoAnalysisRequest) -> VideoAnalysisResult:
        return VideoAnalysisResult(
            status=VisionAnalysisStatus.UNAVAILABLE,
            provider="local",
            frames_analyzed=0,
            pose_findings=[],
            detection_findings=[],
            error=(
                "Adaptador LOCAL nao inclui motor de visao computacional "
                "(OpenPose/YOLOv8). Analise real requer "
                "VISION_PROVIDER=OPENPOSE_YOLOV8 no worker de video."
            ),
        )
