"""Adaptador real de analise de sentimento via Azure AI Language (Text
Analytics - `SentimentAnalysis` + `KeyPhraseExtraction`).

Uso de `httpx` encapsulado neste adaptador - o dominio
(`app.processors.text`, `app.processors.audio`) so ve
`SentimentAnalysisAdapter` (Protocol), nunca o cliente HTTP diretamente.

Esta API e SINCRONA e recebe o texto diretamente
(sem upload nem referencia a storage) - por isso o adaptador nao depende
de storage, mesma caracteristica do adaptador AWS equivalente.

Alem do sentimento, este adaptador tambem chama `KeyPhraseExtraction` (uma
segunda requisicao ao mesmo endpoint `:analyze-text`, trocando apenas
`kind`) para identificar termos/frases-chave do texto - cobre literalmente
o requisito "identificar termos criticos... com Azure Text Analytics".
Isso e ADICIONAL ao motor de termos clinicos proprio do projeto
(`app.clinical_nlp.text_analysis`, NegEx/ConText com negacao/temporalidade/
certeza) - os termos-chave do Azure sao frases genericas de destaque, sem
a mesma analise linguistica estruturada, e por isso ficam gravados como
outro campo do mesmo achado, nunca substituindo o motor proprio.

Limite de tamanho da API (documento unico): 5.120 caracteres. Textos
maiores sao truncados aqui (nunca paginados), mesmo principio de
honestidade dos demais adaptadores reais do projeto.

**Nao exercitado contra a API real do Azure neste ambiente** (sem
credenciais/rede nos testes automatizados) - testado com um cliente HTTP
falso injetado (`tests/test_sentiment_analysis_adapters.py`).
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.enums import SentimentAnalysisStatus
from app.integrations.sentiment_analysis.base import (
    SentimentAnalysisRequest,
    SentimentAnalysisResult,
    SentimentScore,
)

# Limite documentado da API (caracteres, nao bytes) - ver "Data limits" do
# Azure AI Language.
_MAX_TEXT_CHARACTERS = 5120


class _HttpResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...
    @property
    def text(self) -> str: ...


class _HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> _HttpResponse: ...


def _truncate_to_char_limit(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[:max_chars]


class AzureLanguageSentimentAdapter:
    def __init__(
        self,
        *,
        http_client: _HttpClient,
        subscription_key: str,
        endpoint: str,
        api_version: str = "2023-04-01",
    ) -> None:
        self._http = http_client
        self._subscription_key = subscription_key
        self._endpoint = endpoint.rstrip("/")
        self._api_version = api_version

    def detect_sentiment(self, request: SentimentAnalysisRequest) -> SentimentAnalysisResult:
        text = _truncate_to_char_limit(request.text, _MAX_TEXT_CHARACTERS)
        if not text.strip():
            return self._failed_result("Texto vazio apos truncamento - nada a analisar.")

        url = f"{self._endpoint}/language/:analyze-text?api-version={self._api_version}"
        # "pt" cobre tanto pt-BR quanto pt-PT no Azure AI Language (nao ha
        # variante regional separada nesta API, diferente do Transcribe/
        # Speech) - mesmo codigo curto ja usado por `SentimentAnalysisRequest.
        # language_code` (default "pt").
        language_code = request.language_code.split("-")[0]

        try:
            response = self._http.post(
                url,
                headers={
                    "Ocp-Apim-Subscription-Key": self._subscription_key,
                    "Content-Type": "application/json",
                },
                json={
                    "kind": "SentimentAnalysis",
                    "parameters": {"modelVersion": "latest"},
                    "analysisInput": {
                        "documents": [{"id": "1", "language": language_code, "text": text}]
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001 - erro de fornecedor nunca propaga cru
            return self._failed_result(f"Falha ao chamar Azure Language SentimentAnalysis: {exc}")

        if response.status_code != 200:
            return self._failed_result(
                f"Azure Language SentimentAnalysis retornou HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        try:
            payload = response.json()
            document = payload["results"]["documents"][0]
            confidence = document["confidenceScores"]
            sentiment = str(document["sentiment"]).upper()
            scores = SentimentScore(
                positive=float(confidence["positive"]),
                negative=float(confidence["negative"]),
                neutral=float(confidence["neutral"]),
                # Azure nao tem categoria "mixed" separada - documentado
                # como 0.0 explicito em vez de inventar um valor.
                mixed=0.0,
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            return self._failed_result(f"Falha ao interpretar resposta do Azure Language: {exc}")

        # Key Phrase Extraction e uma chamada SEPARADA (kind diferente no
        # mesmo endpoint sincrono) - falha aqui nunca descarta o
        # sentimento ja obtido acima; sem termos-chave, so fica `None`
        # em vez de vazar um erro parcial como falha total do adaptador.
        key_phrases = self._extract_key_phrases(text=text, language_code=language_code)

        return SentimentAnalysisResult(
            status=SentimentAnalysisStatus.COMPLETED,
            provider="azure_language",
            sentiment=sentiment,
            scores=scores,
            key_phrases=key_phrases,
        )

    def _extract_key_phrases(self, *, text: str, language_code: str) -> tuple[str, ...] | None:
        url = f"{self._endpoint}/language/:analyze-text?api-version={self._api_version}"
        try:
            response = self._http.post(
                url,
                headers={
                    "Ocp-Apim-Subscription-Key": self._subscription_key,
                    "Content-Type": "application/json",
                },
                json={
                    "kind": "KeyPhraseExtraction",
                    "parameters": {"modelVersion": "latest"},
                    "analysisInput": {
                        "documents": [{"id": "1", "language": language_code, "text": text}]
                    },
                },
            )
            if response.status_code != 200:
                return None
            payload = response.json()
            phrases = payload["results"]["documents"][0]["keyPhrases"]
            return tuple(str(phrase) for phrase in phrases)
        except Exception:  # noqa: BLE001 - enriquecimento opcional, nunca derruba o sentimento
            return None

    def _failed_result(self, error: str) -> SentimentAnalysisResult:
        return SentimentAnalysisResult(
            status=SentimentAnalysisStatus.FAILED,
            provider="azure_language",
            error=error[:500],
        )
