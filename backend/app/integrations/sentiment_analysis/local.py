"""Adaptador LOCAL de analise de sentimento: honesto sobre nao chamar o
Azure AI Language.

TEMPORARIO (mesmo padrao dos demais adaptadores locais). Retornar um
sentimento fabricado seria pior do que nao analisar (viola o principio
"nunca fingir" usado em todo o projeto). Por isso este adaptador sempre
retorna `SentimentAnalysisStatus.UNAVAILABLE`, nunca `COMPLETED`.
"""

from __future__ import annotations

from app.core.enums import SentimentAnalysisStatus
from app.integrations.sentiment_analysis.base import (
    SentimentAnalysisRequest,
    SentimentAnalysisResult,
)


class LocalUnavailableSentimentAnalysisAdapter:
    def detect_sentiment(self, request: SentimentAnalysisRequest) -> SentimentAnalysisResult:
        return SentimentAnalysisResult(
            status=SentimentAnalysisStatus.UNAVAILABLE,
            provider="local",
            error=(
                "Adaptador LOCAL nao inclui analise de sentimento (Azure AI "
                "Language). Enriquecimento real requer a feature flag "
                "'sentiment_analysis_enabled' ligada e credenciais Azure configuradas."
            ),
        )
