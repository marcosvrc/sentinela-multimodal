"""Testes dos adaptadores de reconhecimento de imagem (Amazon Rekognition
Image, ADR 0016 "atualizacao").

O adaptador LOCAL e testado diretamente (sem rede). O adaptador AWS real
(`AwsRekognitionImageAdapter`) e testado com um cliente `boto3` FALSO
injetado no construtor (mesmo padrao de injecao de dependencia usado em
`test_transcription_adapters.py`).
"""

from __future__ import annotations

from app.core.enums import VisionAnalysisStatus
from app.integrations.image_recognition.aws_rekognition import AwsRekognitionImageAdapter
from app.integrations.image_recognition.base import ImageRecognitionRequest
from app.integrations.image_recognition.local import LocalUnavailableImageRecognitionAdapter

_REQUEST = ImageRecognitionRequest(storage_key="institution-1/analysis-1/foto.png")


def test_local_adapter_always_returns_unavailable_never_fake_labels() -> None:
    adapter = LocalUnavailableImageRecognitionAdapter()
    result = adapter.detect_labels(_REQUEST)

    assert result.status is VisionAnalysisStatus.UNAVAILABLE
    assert result.labels == []
    assert result.provider == "local"
    assert result.error is not None


class _FakeRekognitionClient:
    def __init__(self, *, labels: list[dict] | None = None):
        self.labels = (
            labels
            if labels is not None
            else [
                {"Name": "Person", "Confidence": 91.2},
                {"Name": "X-Ray", "Confidence": 63.5},
            ]
        )
        self.calls: list[dict] = []

    def detect_labels(self, **kwargs):
        self.calls.append(kwargs)
        return {"Labels": self.labels}


def test_aws_adapter_calls_detect_labels_with_approved_prefix() -> None:
    client = _FakeRekognitionClient()
    adapter = AwsRekognitionImageAdapter(
        rekognition_client=client, media_bucket="sentinelhealth-media"
    )

    result = adapter.detect_labels(_REQUEST)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["Image"]["S3Object"]["Bucket"] == "sentinelhealth-media"
    # O objeto so existe em s3://.../approved/... apos `S3StorageAdapter.
    # promote()` (app/storage/s3.py).
    assert call["Image"]["S3Object"]["Name"] == "approved/institution-1/analysis-1/foto.png"
    assert result.status is VisionAnalysisStatus.COMPLETED
    assert result.provider == "aws_rekognition"


def test_aws_adapter_returns_completed_result_with_parsed_labels() -> None:
    adapter = AwsRekognitionImageAdapter(
        rekognition_client=_FakeRekognitionClient(
            labels=[{"Name": "Document", "Confidence": 77.0}]
        ),
        media_bucket="bucket",
    )

    result = adapter.detect_labels(_REQUEST)

    assert result.status is VisionAnalysisStatus.COMPLETED
    assert len(result.labels) == 1
    assert result.labels[0].label == "Document"
    assert result.labels[0].confidence == 77.0


def test_aws_adapter_never_raises_when_client_errors() -> None:
    class _RaisingClient:
        def detect_labels(self, **kwargs):
            raise RuntimeError("credenciais invalidas")

    adapter = AwsRekognitionImageAdapter(rekognition_client=_RaisingClient(), media_bucket="bucket")

    result = adapter.detect_labels(_REQUEST)

    assert result.status is VisionAnalysisStatus.FAILED
    assert "credenciais invalidas" in result.error
    assert result.labels == []


class _FakeAzureHttpResponse:
    def __init__(self, *, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _FakeAzureVisionHttpClient:
    def __init__(self, *, response: _FakeAzureHttpResponse):
        self.response = response
        self.calls: list[dict] = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


def test_azure_adapter_sends_image_bytes_and_returns_completed_labels() -> None:
    from app.integrations.image_recognition.azure_vision import AzureVisionAdapter

    response = _FakeAzureHttpResponse(
        status_code=200,
        payload={"tagsResult": {"values": [{"name": "person", "confidence": 0.912}]}},
    )
    client = _FakeAzureVisionHttpClient(response=response)
    adapter = AzureVisionAdapter(
        http_client=client,
        subscription_key="key",
        endpoint="https://example.cognitiveservices.azure.com/",
    )

    request = ImageRecognitionRequest(
        storage_key="institution-1/analysis-1/foto.png", image_bytes=b"fake-png-bytes"
    )
    result = adapter.detect_labels(request)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert "imageanalysis:analyze" in call["url"]
    assert call["content"] == b"fake-png-bytes"
    assert result.status is VisionAnalysisStatus.COMPLETED
    assert result.provider == "azure_vision"
    assert len(result.labels) == 1
    assert result.labels[0].label == "person"
    assert result.labels[0].confidence == 91.2


def test_azure_adapter_fails_without_image_bytes() -> None:
    from app.integrations.image_recognition.azure_vision import AzureVisionAdapter

    adapter = AzureVisionAdapter(
        http_client=_FakeAzureVisionHttpClient(response=_FakeAzureHttpResponse(status_code=200)),
        subscription_key="key",
        endpoint="https://example.cognitiveservices.azure.com/",
    )

    result = adapter.detect_labels(ImageRecognitionRequest(storage_key="foto.png"))

    assert result.status is VisionAnalysisStatus.FAILED
    assert "image_bytes" in result.error


def test_azure_adapter_returns_failed_result_on_non_200_response() -> None:
    from app.integrations.image_recognition.azure_vision import AzureVisionAdapter

    client = _FakeAzureVisionHttpClient(
        response=_FakeAzureHttpResponse(status_code=403, text="Forbidden")
    )
    adapter = AzureVisionAdapter(
        http_client=client,
        subscription_key="key",
        endpoint="https://example.cognitiveservices.azure.com/",
    )

    result = adapter.detect_labels(
        ImageRecognitionRequest(storage_key="foto.png", image_bytes=b"fake-bytes")
    )

    assert result.status is VisionAnalysisStatus.FAILED
    assert "403" in result.error
