"""Testes dos adaptadores de reconhecimento de imagem (Azure AI Vision
Image Analysis).

O adaptador LOCAL e testado diretamente (sem rede). O adaptador Azure real
(`AzureVisionAdapter`) e testado com um cliente HTTP FALSO injetado no
construtor (mesmo padrao de injecao de dependencia usado em
`test_transcription_adapters.py`).
"""

from __future__ import annotations

from app.core.enums import VisionAnalysisStatus
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
