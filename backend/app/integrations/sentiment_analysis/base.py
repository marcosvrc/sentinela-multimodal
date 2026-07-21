"""Contrato do adaptador de analise de sentimento (Azure AI Language
`SentimentAnalysis`/`KeyPhraseExtraction`). Analise de sentimento, quando
utilizada, e sempre apenas contextual e nunca determina risco clinico.

Mesmo padrao arquitetural dos demais adaptadores reais do projeto
(`app.integrations.image_recognition`, `app.integrations.transcription`):
o dominio (`app.processors.text`, `app.processors.audio`) depende apenas
deste Protocol, nunca do cliente HTTP diretamente.

O Azure AI Language usado aqui suporta portugues (`pt`) - por isso e
viavel para a cadeia principal do projeto, que opera em portugues
brasileiro.

Resultado sempre CONTEXTUAL: o sentimento detectado (positivo/negativo/
neutro/misto) e um dado adicional exibido ao profissional, nunca um
achado que altera `risk_level` ou entra no prompt do LLM de consolidacao
de risco - unico ponto de insercao permitido e `app.reports.builder`,
como observacoes derivadas dos modelos no laudo.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.enums import SentimentAnalysisStatus


@dataclass(frozen=True)
class SentimentAnalysisRequest:
    """Texto ja disponivel no processo (texto adicional da analise, ou
    transcricao de audio ja obtida) - nunca uma referencia a arquivo:
    `DetectSentiment` opera sobre texto UTF-8 direto, sem upload prévio."""

    text: str
    language_code: str = "pt"


@dataclass(frozen=True)
class SentimentScore:
    """Confianca (0-1) de cada uma das quatro categorias fixas do
    provedor - sempre somam ~1.0, exibidas para dar transparencia sobre
    o quao decisivo foi o sentimento dominante."""

    positive: float
    negative: float
    neutral: float
    mixed: float


@dataclass(frozen=True)
class SentimentAnalysisResult:
    status: SentimentAnalysisStatus
    provider: str
    sentiment: str | None = None  # "POSITIVE" | "NEGATIVE" | "NEUTRAL" | "MIXED"
    scores: SentimentScore | None = None
    error: str | None = None
    # Termos-chave identificados no texto (Azure AI Language - Key Phrase
    # Extraction). `None` quando a extracao falhar isoladamente - nunca
    # uma lista vazia fabricada para "parecer" que a extracao rodou.
    # Sempre CONTEXTUAL, mesmo principio do sentimento: nunca determina
    # risco clinico nem substitui `app.clinical_nlp.text_analysis` (motor
    # NegEx/ConText proprio, que continua sendo a fonte de termos
    # clinicos com negacao/temporalidade/certeza).
    key_phrases: tuple[str, ...] | None = None


class SentimentAnalysisAdapter(Protocol):
    """Implementado por `LocalUnavailableSentimentAnalysisAdapter` (dev/
    testes) e `AzureLanguageSentimentAdapter` (real)."""

    def detect_sentiment(self, request: SentimentAnalysisRequest) -> SentimentAnalysisResult: ...
