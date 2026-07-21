"""Adaptador LOCAL de reconhecimento de video: honesto sobre nao chamar o
Rekognition Video.

TEMPORARIO (mesmo padrao dos demais adaptadores locais). Sempre retorna
`VisionAnalysisStatus.UNAVAILABLE`, nunca `COMPLETED`, com lista de
rotulos vazia - nunca fabrica um rotulo ou timestamp.
"""

from __future__ import annotations

from app.core.enums import VisionAnalysisStatus
from app.integrations.video_recognition.base import (
    VideoRecognitionRequest,
    VideoRecognitionResult,
)


class LocalUnavailableVideoRecognitionAdapter:
    def detect_labels(self, request: VideoRecognitionRequest) -> VideoRecognitionResult:
        return VideoRecognitionResult(
            status=VisionAnalysisStatus.UNAVAILABLE,
            provider="local",
            job_name=request.job_name,
            labels=[],
            error=(
                "Adaptador LOCAL nao inclui reconhecimento de video (Amazon "
                "Rekognition Video). Enriquecimento real requer a feature flag "
                "'vision_rekognition_video_enabled' ligada e credenciais AWS configuradas."
            ),
        )
