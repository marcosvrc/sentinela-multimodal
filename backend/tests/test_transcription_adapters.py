"""Testes dos adaptadores de transcricao (secao 4.2/6.2 do escopo).

O adaptador LOCAL e testado diretamente (sem rede). O adaptador Azure real
(`AzureSpeechAdapter`) e testado com um cliente HTTP FALSO injetado no
construtor (mesmo padrao de injecao de dependencia usado no restante do
projeto) - verifica construcao da requisicao e parsing da resposta sem
tocar a Azure de verdade, que nao esta disponivel neste sandbox.
"""

from __future__ import annotations

from app.core.enums import TranscriptionStatus
from app.integrations.transcription.base import TranscriptionRequest
from app.integrations.transcription.local import LocalUnavailableTranscriptionAdapter

_REQUEST = TranscriptionRequest(
    storage_key="institution-1/analysis-1/audio.wav",
    language_code="pt-BR",
    media_format="wav",
    job_name="analysis-1-audio",
)


def test_local_adapter_always_returns_unavailable_never_a_fake_transcript() -> None:
    adapter = LocalUnavailableTranscriptionAdapter()
    result = adapter.transcribe(_REQUEST)

    assert result.status is TranscriptionStatus.UNAVAILABLE
    assert result.transcript_text is None
    assert result.provider == "local"
    assert result.error is not None


class _FakeHttpResponse:
    def __init__(self, *, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeAzureSpeechHttpClient:
    def __init__(self, *, response: _FakeHttpResponse):
        self.response = response
        self.calls: list[dict] = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_azure_adapter_sends_audio_bytes_and_returns_completed_transcript() -> None:
    from app.integrations.transcription.azure_speech import AzureSpeechAdapter

    response = _FakeHttpResponse(
        status_code=200,
        payload={"combinedPhrases": [{"text": "paciente relata cansaco"}]},
    )
    client = _FakeAzureSpeechHttpClient(response=response)
    adapter = AzureSpeechAdapter(http_client=client, subscription_key="key", region="eastus")

    request = TranscriptionRequest(
        storage_key="institution-1/analysis-1/audio.wav",
        language_code="pt-BR",
        media_format="wav",
        job_name="analysis-1-audio",
        audio_bytes=b"RIFF....WAVEfmt ",
    )
    result = adapter.transcribe(request)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert "eastus.api.cognitive.microsoft.com" in call["url"]
    assert call["files"]["audio"][1] == b"RIFF....WAVEfmt "
    assert result.status is TranscriptionStatus.COMPLETED
    assert result.transcript_text == "paciente relata cansaco"
    assert result.provider == "azure_speech"


def test_azure_adapter_returns_failed_result_on_non_200_response() -> None:
    from app.integrations.transcription.azure_speech import AzureSpeechAdapter

    client = _FakeAzureSpeechHttpClient(
        response=_FakeHttpResponse(status_code=401, text="Access denied")
    )
    adapter = AzureSpeechAdapter(http_client=client, subscription_key="key", region="eastus")

    result = adapter.transcribe(
        TranscriptionRequest(
            storage_key="institution-1/analysis-1/audio.wav",
            language_code="pt-BR",
            media_format="wav",
            job_name="analysis-1-audio",
            audio_bytes=b"fake-bytes",
        )
    )

    assert result.status is TranscriptionStatus.FAILED
    assert "401" in result.error


def test_azure_adapter_never_raises_when_client_errors() -> None:
    from app.integrations.transcription.azure_speech import AzureSpeechAdapter

    class _RaisingClient:
        def post(self, *args, **kwargs):
            raise RuntimeError("credenciais invalidas")

    adapter = AzureSpeechAdapter(
        http_client=_RaisingClient(), subscription_key="key", region="eastus"
    )

    result = adapter.transcribe(
        TranscriptionRequest(
            storage_key="institution-1/analysis-1/audio.wav",
            language_code="pt-BR",
            media_format="wav",
            job_name="analysis-1-audio",
            audio_bytes=b"fake-bytes",
        )
    )

    assert result.status is TranscriptionStatus.FAILED
    assert "credenciais invalidas" in result.error
