"""Adaptador real de analise de sentimento via Amazon Comprehend.

Uso do `boto3` encapsulado neste adaptador - o dominio
(`app.processors.text`, `app.processors.audio`) so ve
`SentimentAnalysisAdapter` (Protocol). `DetectSentiment` e SINCRONO e
recebe o texto diretamente (nao ha upload nem referencia a S3, diferente
do Rekognition Image) - por isso o adaptador nao depende de storage.

Limite de tamanho do Comprehend: `DetectSentiment` aceita no maximo 5.000
bytes UTF-8 por chamada. Textos maiores sao truncados aqui (nunca
enviados em lote/paginados) - o suficiente para o caso de uso (texto
adicional de uma analise ou transcricao de um audio de consulta, ambos
tipicamente curtos), documentado explicitamente em vez de escondido.

**Nao exercitado contra a API real da AWS neste ambiente** (sem
credenciais/rede) - testado com um cliente `boto3` falso injetado
(`tests/test_sentiment_analysis_adapters.py`), verificando construcao da
requisicao e parsing da resposta.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.enums import SentimentAnalysisStatus
from app.integrations.sentiment_analysis.base import (
    SentimentAnalysisRequest,
    SentimentAnalysisResult,
    SentimentScore,
)

# Limite documentado da API (bytes UTF-8, nao caracteres) - ver
# "Guidelines and limits" do Amazon Comprehend.
_MAX_TEXT_BYTES = 5000


class _ComprehendClient(Protocol):
    def detect_sentiment(self, **kwargs: Any) -> dict: ...


def _truncate_to_byte_limit(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    # Corta em bytes e decodifica de volta ignorando um possivel byte
    # multibyte cortado no meio (nunca falha por caractere incompleto).
    return encoded[:max_bytes].decode("utf-8", errors="ignore")


class AwsComprehendSentimentAdapter:
    def __init__(self, *, comprehend_client: _ComprehendClient):
        self._comprehend = comprehend_client

    def detect_sentiment(self, request: SentimentAnalysisRequest) -> SentimentAnalysisResult:
        text = _truncate_to_byte_limit(request.text, _MAX_TEXT_BYTES)
        if not text.strip():
            return self._failed_result("Texto vazio apos truncamento - nada a analisar.")

        try:
            response = self._comprehend.detect_sentiment(
                Text=text, LanguageCode=request.language_code
            )
        except Exception as exc:  # noqa: BLE001 - erro de fornecedor nunca propaga cru
            return self._failed_result(f"Falha ao chamar DetectSentiment: {exc}")

        try:
            raw_scores = response["SentimentScore"]
            scores = SentimentScore(
                positive=float(raw_scores["Positive"]),
                negative=float(raw_scores["Negative"]),
                neutral=float(raw_scores["Neutral"]),
                mixed=float(raw_scores["Mixed"]),
            )
            sentiment = str(response["Sentiment"])
        except (KeyError, TypeError, ValueError) as exc:
            return self._failed_result(f"Falha ao interpretar resposta do Comprehend: {exc}")

        return SentimentAnalysisResult(
            status=SentimentAnalysisStatus.COMPLETED,
            provider="aws_comprehend",
            sentiment=sentiment,
            scores=scores,
        )

    def _failed_result(self, error: str) -> SentimentAnalysisResult:
        return SentimentAnalysisResult(
            status=SentimentAnalysisStatus.FAILED,
            provider="aws_comprehend",
            error=error[:500],
        )
