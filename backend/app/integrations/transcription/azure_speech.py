"""Adaptador real de transcricao via Azure AI Speech (Fast Transcription API).

Uso de `httpx` encapsulado neste adaptador - o dominio
(`app.processors.audio`) so ve `TranscriptionAdapter` (Protocol), nunca o
cliente HTTP diretamente.

A Fast Transcription API do Azure e SINCRONA e recebe os bytes do audio
diretamente no corpo `multipart/form-data` da requisicao (campo `audio`)
- nao ha upload previo a um storage do provedor nem polling. Isso
elimina a necessidade de gerar uma SAS URL do Blob Storage (a alternativa
seria a Batch Transcription API, que exige URL publica ou SAS) - a Fast
Transcription API aceita o arquivo aprovado lido direto do
`StorageAdapter` do projeto (filesystem local).

Limites documentados da API: audio com no maximo 2 horas de duracao e
250 MB de tamanho - bem acima do que este projeto trata (ver
`MAX_SIZE_BYTES[ModalityType.AUDIO]` em `app.media.validation`, 200 MB).

**Nao exercitado contra a API real do Azure neste ambiente** (sem
credenciais/rede nos testes automatizados) - testado com um cliente HTTP
falso injetado (`tests/test_transcription_adapters.py`), verificando
construcao da requisicao e parsing da resposta.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from app.core.enums import TranscriptionStatus
from app.integrations.transcription.base import TranscriptionRequest, TranscriptionResult

# Content-Types aceitos pela API a partir da extensao do arquivo aprovado
# (mesma logica de `media_format` usada pelo `AwsTranscribeAdapter`) - a
# Fast Transcription API detecta o formato pelo conteudo do arquivo, mas
# enviar o Content-Type correto no multipart evita ambiguidade.
_CONTENT_TYPE_BY_FORMAT: dict[str, str] = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "mp4": "audio/mp4",
}


class _HttpResponse(Protocol):
    status_code: int

    def json(self) -> Any: ...
    @property
    def text(self) -> str: ...


class _HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> _HttpResponse: ...


class AzureSpeechAdapter:
    def __init__(
        self,
        *,
        http_client: _HttpClient,
        subscription_key: str,
        region: str,
        api_version: str = "2025-10-15",
    ) -> None:
        self._http = http_client
        self._subscription_key = subscription_key
        self._region = region
        self._api_version = api_version

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        content_type = _CONTENT_TYPE_BY_FORMAT.get(request.media_format, "application/octet-stream")
        url = (
            f"https://{self._region}.api.cognitive.microsoft.com/speechtotext/"
            f"transcriptions:transcribe?api-version={self._api_version}"
        )
        # `definition` e um campo de formulario com um JSON serializado
        # (ver referencia REST) - so a locale e necessaria aqui, sem
        # diarizacao/timestamps por palavra (nao usados pelo dominio).
        definition = json.dumps({"locales": [request.language_code]})

        try:
            response = self._http.post(
                url,
                headers={"Ocp-Apim-Subscription-Key": self._subscription_key},
                files={
                    "audio": (
                        f"{request.job_name}.{request.media_format}",
                        request.audio_bytes,
                        content_type,
                    )
                },
                data={"definition": definition},
            )
        except Exception as exc:  # noqa: BLE001 - erro de fornecedor nunca propaga cru
            return self._failed_result(request, f"Falha ao chamar Fast Transcription API: {exc}")

        if response.status_code != 200:
            detail = f"HTTP {response.status_code}: {response.text[:300]}"
            return self._failed_result(request, f"Fast Transcription API retornou {detail}")

        try:
            payload = response.json()
            combined_phrases = payload.get("combinedPhrases", [])
            transcript_text = " ".join(
                phrase["text"] for phrase in combined_phrases if phrase.get("text")
            ).strip()
        except (KeyError, TypeError, ValueError) as exc:
            return self._failed_result(
                request, f"Falha ao interpretar resposta do Azure Speech: {exc}"
            )

        if not transcript_text:
            return self._failed_result(
                request, "Transcricao vazia (nenhuma fala detectada no audio)."
            )

        return TranscriptionResult(
            status=TranscriptionStatus.COMPLETED,
            transcript_text=transcript_text,
            provider="azure_speech",
            engine="azure-speech-fast-transcription",
            language_code=request.language_code,
            job_name=request.job_name,
        )

    def _failed_result(self, request: TranscriptionRequest, error: str) -> TranscriptionResult:
        return TranscriptionResult(
            status=TranscriptionStatus.FAILED,
            transcript_text=None,
            provider="azure_speech",
            engine="azure-speech-fast-transcription",
            language_code=request.language_code,
            job_name=request.job_name,
            error=error[:500],
        )
