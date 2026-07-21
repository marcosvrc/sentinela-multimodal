"""Adaptador LOCAL de reconhecimento de imagem: honesto sobre nao chamar
o Azure AI Vision.

TEMPORARIO (mesmo padrao dos demais adaptadores locais). Retornar rotulos
fabricados seria pior do que nao rotular (viola o principio "nunca fingir"
usado em todo o projeto). Por isso este adaptador sempre retorna
`VisionAnalysisStatus.UNAVAILABLE`, nunca `COMPLETED`, com lista de
rotulos vazia.
"""

from __future__ import annotations

from app.core.enums import VisionAnalysisStatus
from app.integrations.image_recognition.base import (
    ImageRecognitionRequest,
    ImageRecognitionResult,
)


class LocalUnavailableImageRecognitionAdapter:
    def detect_labels(self, request: ImageRecognitionRequest) -> ImageRecognitionResult:
        return ImageRecognitionResult(
            status=VisionAnalysisStatus.UNAVAILABLE,
            provider="local",
            labels=[],
            error=(
                "Adaptador LOCAL nao inclui reconhecimento de imagem (Azure AI "
                "Vision). Enriquecimento real requer a feature flag "
                "'image_recognition_enabled' ligada e credenciais Azure configuradas."
            ),
        )
