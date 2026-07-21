"""Testes dos adaptadores de analise de sentimento (Azure AI Language
`SentimentAnalysis`/`KeyPhraseExtraction`).

O adaptador LOCAL e testado diretamente (sem rede). O adaptador Azure real
(`AzureLanguageSentimentAdapter`) e testado com um cliente HTTP FALSO
injetado no construtor (mesmo padrao de `test_transcription_adapters.py`)."""

from __future__ import annotations

from app.core.enums import SentimentAnalysisStatus
from app.integrations.sentiment_analysis.base import SentimentAnalysisRequest
from app.integrations.sentiment_analysis.local import LocalUnavailableSentimentAnalysisAdapter

_REQUEST = SentimentAnalysisRequest(text="Paciente relata cansaco e falta de animo.")


def test_local_adapter_always_returns_unavailable_never_fake_sentiment() -> None:
    adapter = LocalUnavailableSentimentAnalysisAdapter()
    result = adapter.detect_sentiment(_REQUEST)

    assert result.status is SentimentAnalysisStatus.UNAVAILABLE
    assert result.sentiment is None
    assert result.scores is None
    assert result.provider == "local"
    assert result.error is not None


class _FakeAzureHttpResponse:
    def __init__(self, *, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeAzureLanguageHttpClient:
    def __init__(self, *, responses: list[_FakeAzureHttpResponse]):
        # Uma resposta por chamada, na ordem: SentimentAnalysis, depois
        # KeyPhraseExtraction (ver `_extract_key_phrases`) - permite
        # simular os dois "kinds" sem inspecionar o corpo da requisicao.
        self._responses = list(responses)
        self.calls: list[dict] = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self._responses.pop(0)


def test_azure_adapter_calls_analyze_text_and_returns_completed_result() -> None:
    from app.integrations.sentiment_analysis.azure_language import AzureLanguageSentimentAdapter

    sentiment_response = _FakeAzureHttpResponse(
        status_code=200,
        payload={
            "results": {
                "documents": [
                    {
                        "sentiment": "negative",
                        "confidenceScores": {"positive": 0.02, "negative": 0.85, "neutral": 0.13},
                    }
                ]
            }
        },
    )
    key_phrases_response = _FakeAzureHttpResponse(
        status_code=200,
        payload={"results": {"documents": [{"keyPhrases": ["cansaço", "falta de animo"]}]}},
    )
    client = _FakeAzureLanguageHttpClient(responses=[sentiment_response, key_phrases_response])
    adapter = AzureLanguageSentimentAdapter(
        http_client=client,
        subscription_key="key",
        endpoint="https://example.cognitiveservices.azure.com/",
    )

    result = adapter.detect_sentiment(_REQUEST)

    assert len(client.calls) == 2
    first_call, second_call = client.calls
    assert "analyze-text" in first_call["url"]
    assert first_call["json"]["kind"] == "SentimentAnalysis"
    assert second_call["json"]["kind"] == "KeyPhraseExtraction"
    assert result.status is SentimentAnalysisStatus.COMPLETED
    assert result.provider == "azure_language"
    assert result.sentiment == "NEGATIVE"
    assert result.scores is not None
    assert result.scores.negative == 0.85
    assert result.scores.mixed == 0.0
    assert result.key_phrases == ("cansaço", "falta de animo")


def test_azure_adapter_returns_none_key_phrases_when_extraction_fails() -> None:
    from app.integrations.sentiment_analysis.azure_language import AzureLanguageSentimentAdapter

    sentiment_response = _FakeAzureHttpResponse(
        status_code=200,
        payload={
            "results": {
                "documents": [
                    {
                        "sentiment": "positive",
                        "confidenceScores": {"positive": 0.9, "negative": 0.05, "neutral": 0.05},
                    }
                ]
            }
        },
    )
    key_phrases_response = _FakeAzureHttpResponse(status_code=500, text="Internal error")
    client = _FakeAzureLanguageHttpClient(responses=[sentiment_response, key_phrases_response])
    adapter = AzureLanguageSentimentAdapter(
        http_client=client,
        subscription_key="key",
        endpoint="https://example.cognitiveservices.azure.com/",
    )

    result = adapter.detect_sentiment(_REQUEST)

    # Sentimento continua COMPLETED mesmo com a extracao de termos-chave
    # falhando - sao chamadas independentes, uma nao deve derrubar a outra.
    assert result.status is SentimentAnalysisStatus.COMPLETED
    assert result.sentiment == "POSITIVE"
    assert result.key_phrases is None


def test_azure_adapter_returns_failed_result_on_non_200_response() -> None:
    from app.integrations.sentiment_analysis.azure_language import AzureLanguageSentimentAdapter

    client = _FakeAzureLanguageHttpClient(
        responses=[_FakeAzureHttpResponse(status_code=401, text="Unauthorized")]
    )
    adapter = AzureLanguageSentimentAdapter(
        http_client=client,
        subscription_key="key",
        endpoint="https://example.cognitiveservices.azure.com/",
    )

    result = adapter.detect_sentiment(_REQUEST)

    assert result.status is SentimentAnalysisStatus.FAILED
    assert "401" in result.error


def test_azure_adapter_fails_gracefully_on_empty_text() -> None:
    from app.integrations.sentiment_analysis.azure_language import AzureLanguageSentimentAdapter

    adapter = AzureLanguageSentimentAdapter(
        http_client=_FakeAzureLanguageHttpClient(
            responses=[_FakeAzureHttpResponse(status_code=200)]
        ),
        subscription_key="key",
        endpoint="https://example.cognitiveservices.azure.com/",
    )

    result = adapter.detect_sentiment(SentimentAnalysisRequest(text="   "))

    assert result.status is SentimentAnalysisStatus.FAILED
    assert result.sentiment is None
