"""Selecao do adaptador de transcricao por configuracao (mesmo padrao de
app.integrations.llm)."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.enums import TranscriptionProvider
from app.integrations.transcription.base import TranscriptionAdapter
from app.integrations.transcription.local import LocalUnavailableTranscriptionAdapter


@lru_cache
def get_transcription_adapter() -> TranscriptionAdapter:
    settings = get_settings()

    if settings.transcription_provider is TranscriptionProvider.LOCAL:
        return LocalUnavailableTranscriptionAdapter()

    if settings.transcription_provider is TranscriptionProvider.AZURE_SPEECH:
        if not settings.azure_speech_key or not settings.azure_speech_region:
            raise RuntimeError(
                "transcription_provider=AZURE_SPEECH exige AZURE_SPEECH_KEY e "
                "AZURE_SPEECH_REGION configurados."
            )

        import httpx

        from app.integrations.transcription.azure_speech import AzureSpeechAdapter

        return AzureSpeechAdapter(
            http_client=httpx.Client(timeout=60.0),  # type: ignore[arg-type]
            subscription_key=settings.azure_speech_key,
            region=settings.azure_speech_region,
        )

    raise RuntimeError(f"Provedor de transcricao desconhecido: {settings.transcription_provider}")
