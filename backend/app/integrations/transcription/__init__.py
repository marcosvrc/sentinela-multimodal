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

    if settings.transcription_provider is TranscriptionProvider.AWS_TRANSCRIBE:
        if not settings.s3_media_bucket or not settings.transcription_output_bucket:
            raise RuntimeError(
                "transcription_provider=AWS_TRANSCRIBE exige S3_MEDIA_BUCKET e "
                "TRANSCRIPTION_OUTPUT_BUCKET configurados."
            )

        import boto3

        from app.integrations.transcription.aws_transcribe import AwsTranscribeAdapter

        return AwsTranscribeAdapter(
            transcribe_client=boto3.client("transcribe", region_name=settings.aws_region),
            s3_client=boto3.client("s3", region_name=settings.aws_region),
            media_bucket=settings.s3_media_bucket,
            output_bucket=settings.transcription_output_bucket,
        )

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
