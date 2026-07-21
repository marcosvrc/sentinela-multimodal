"""Testes dos adaptadores de transcricao (secao 4.2/6.2 do escopo).

O adaptador LOCAL e testado diretamente (sem rede). O adaptador AWS real
(`AwsTranscribeAdapter`) e testado com um cliente `boto3` FALSO injetado no
construtor (mesmo padrao de injecao de dependencia usado no restante do
projeto) - verifica construcao da requisicao e parsing da resposta sem
tocar a AWS de verdade, que nao esta disponivel neste sandbox.
"""

from __future__ import annotations

import io
import json

from app.core.enums import TranscriptionStatus
from app.integrations.transcription.aws_transcribe import AwsTranscribeAdapter
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


class _FakeTranscribeClient:
    def __init__(self, *, final_status: str = "COMPLETED"):
        self.final_status = final_status
        self.start_calls: list[dict] = []
        self.poll_count = 0

    def start_transcription_job(self, **kwargs):
        self.start_calls.append(kwargs)
        return {"TranscriptionJob": {"TranscriptionJobStatus": "IN_PROGRESS"}}

    def get_transcription_job(self, **kwargs):
        self.poll_count += 1
        return {"TranscriptionJob": {"TranscriptionJobStatus": self.final_status}}


class _FakeS3Client:
    def __init__(self, *, transcript_text: str = "ola, como vai voce"):
        self.transcript_text = transcript_text
        self.get_object_calls: list[dict] = []

    def get_object(self, **kwargs):
        self.get_object_calls.append(kwargs)
        payload = json.dumps({"results": {"transcripts": [{"transcript": self.transcript_text}]}})
        return {"Body": io.BytesIO(payload.encode("utf-8"))}


def test_aws_adapter_starts_job_with_correct_media_uri_and_output() -> None:
    transcribe_client = _FakeTranscribeClient()
    s3_client = _FakeS3Client()
    adapter = AwsTranscribeAdapter(
        transcribe_client=transcribe_client,
        s3_client=s3_client,
        media_bucket="sentinelhealth-media",
        output_bucket="sentinelhealth-transcriptions",
        poll_interval_seconds=0,
    )

    adapter.transcribe(_REQUEST)

    assert len(transcribe_client.start_calls) == 1
    call = transcribe_client.start_calls[0]
    assert call["TranscriptionJobName"] == "analysis-1-audio"
    assert call["LanguageCode"] == "pt-BR"
    assert call["MediaFormat"] == "wav"
    # O objeto so existe em s3://.../approved/... apos `S3StorageAdapter.
    # promote()` (app/storage/s3.py) - o adaptador de transcricao precisa
    # do mesmo prefixo, nunca da chave "nua" salva no banco.
    assert call["Media"]["MediaFileUri"] == (
        "s3://sentinelhealth-media/approved/institution-1/analysis-1/audio.wav"
    )
    assert call["OutputBucketName"] == "sentinelhealth-transcriptions"


def test_aws_adapter_returns_completed_result_with_parsed_transcript() -> None:
    adapter = AwsTranscribeAdapter(
        transcribe_client=_FakeTranscribeClient(),
        s3_client=_FakeS3Client(transcript_text="paciente relata cansaco"),
        media_bucket="bucket",
        output_bucket="output-bucket",
        poll_interval_seconds=0,
    )

    result = adapter.transcribe(_REQUEST)

    assert result.status is TranscriptionStatus.COMPLETED
    assert result.transcript_text == "paciente relata cansaco"
    assert result.provider == "aws_transcribe"


def test_aws_adapter_returns_failed_result_when_job_fails() -> None:
    adapter = AwsTranscribeAdapter(
        transcribe_client=_FakeTranscribeClient(final_status="FAILED"),
        s3_client=_FakeS3Client(),
        media_bucket="bucket",
        output_bucket="output-bucket",
        poll_interval_seconds=0,
    )

    result = adapter.transcribe(_REQUEST)

    assert result.status is TranscriptionStatus.FAILED
    assert result.transcript_text is None
    assert result.error is not None


def test_aws_adapter_never_raises_when_client_errors() -> None:
    class _RaisingTranscribeClient:
        def start_transcription_job(self, **kwargs):
            raise RuntimeError("credenciais invalidas")

    adapter = AwsTranscribeAdapter(
        transcribe_client=_RaisingTranscribeClient(),
        s3_client=_FakeS3Client(),
        media_bucket="bucket",
        output_bucket="output-bucket",
        poll_interval_seconds=0,
    )

    result = adapter.transcribe(_REQUEST)

    assert result.status is TranscriptionStatus.FAILED
    assert "credenciais invalidas" in result.error


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
