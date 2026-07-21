"""Adaptador real de reconhecimento de imagem via Azure AI Vision (Image
Analysis 4.0 - feature `tags`).

Uso de `httpx` encapsulado neste adaptador - o dominio
(`app.processors.image`) so ve `ImageRecognitionAdapter` (Protocol), nunca
o cliente HTTP diretamente.

A API de Image Analysis do Azure recebe os bytes da imagem diretamente no
corpo da requisicao (`Content-Type: application/octet-stream`) - nao ha
upload previo a um Blob Storage. Os bytes ja lidos pelo processador do
storage aprovado (filesystem local) sao reenviados aqui.

**Nao exercitado contra a API real do Azure neste ambiente** (sem
credenciais/rede nos testes automatizados) - testado com um cliente HTTP
falso injetado (`tests/test_image_recognition_adapters.py`).
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.enums import VisionAnalysisStatus
from app.integrations.image_recognition.base import (
    ImageLabelFinding,
    ImageRecognitionRequest,
    ImageRecognitionResult,
)


class _HttpResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...
    @property
    def text(self) -> str: ...


class _HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> _HttpResponse: ...


class AzureVisionAdapter:
    def __init__(
        self,
        *,
        http_client: _HttpClient,
        subscription_key: str,
        endpoint: str,
        api_version: str = "2024-02-01",
    ) -> None:
        self._http = http_client
        self._subscription_key = subscription_key
        # Remove barra final para montar a URL de forma previsivel,
        # independente de como o usuario colou o endpoint no `.env`.
        self._endpoint = endpoint.rstrip("/")
        self._api_version = api_version

    def detect_labels(self, request: ImageRecognitionRequest) -> ImageRecognitionResult:
        if request.image_bytes is None:
            return self._failed_result(
                "Adaptador Azure Vision exige os bytes da imagem (image_bytes) - "
                "referencia por storage_key sem bytes nao e suportada por este provedor."
            )

        url = (
            f"{self._endpoint}/computervision/imageanalysis:analyze"
            f"?features=tags&language=pt&api-version={self._api_version}"
        )

        try:
            response = self._http.post(
                url,
                headers={
                    "Ocp-Apim-Subscription-Key": self._subscription_key,
                    "Content-Type": "application/octet-stream",
                },
                content=request.image_bytes,
            )
        except Exception as exc:  # noqa: BLE001 - erro de fornecedor nunca propaga cru
            return self._failed_result(f"Falha ao chamar Azure Vision Analyze: {exc}")

        if response.status_code != 200:
            return self._failed_result(
                f"Azure Vision Analyze retornou HTTP {response.status_code}: {response.text[:300]}"
            )

        try:
            payload = response.json()
            tag_values = payload.get("tagsResult", {}).get("values", [])
            labels = [
                ImageLabelFinding(
                    label=str(item["name"]), confidence=float(item["confidence"]) * 100.0
                )
                for item in tag_values
                # Azure devolve confianca 0-1; convertido para 0-100 para
                # manter a mesma escala (0-100) usada pelo restante do
                # dominio.
                if float(item["confidence"]) * 100.0 >= request.min_confidence
            ]
        except (KeyError, TypeError, ValueError) as exc:
            return self._failed_result(f"Falha ao interpretar resposta do Azure Vision: {exc}")

        return ImageRecognitionResult(
            status=VisionAnalysisStatus.COMPLETED,
            provider="azure_vision",
            labels=labels,
        )

    def _failed_result(self, error: str) -> ImageRecognitionResult:
        return ImageRecognitionResult(
            status=VisionAnalysisStatus.FAILED,
            provider="azure_vision",
            labels=[],
            error=error[:500],
        )
