"""Contrato do adaptador de transcricao de audio.

Mesmo padrao arquitetural do adaptador de LLM (`app.integrations.llm.base`):
o dominio (`app.processors.audio`) depende apenas deste Protocol, nunca do
cliente HTTP diretamente. `TranscriptionRequest` carrega `audio_bytes`
porque a Azure AI Speech (Fast Transcription API) recebe o arquivo direto
no corpo da requisicao, sem exigir um storage intermediario - o
processador (`app.processors.audio`) ja le os bytes do storage aprovado
para a analise acustica local, entao reaproveita-los aqui nao adiciona
nenhuma leitura extra."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.enums import TranscriptionStatus


@dataclass(frozen=True)
class TranscriptionRequest:
    """`storage_key` identifica o objeto de audio ja aprovado (usado em
    logs/auditoria); `audio_bytes` carrega o conteudo enviado diretamente
    no corpo da requisicao a Fast Transcription API do Azure."""

    storage_key: str
    language_code: str
    media_format: str  # "wav" | "mp3" | "mp4"
    job_name: str
    audio_bytes: bytes | None = None


@dataclass(frozen=True)
class TranscriptionResult:
    status: TranscriptionStatus
    transcript_text: str | None
    provider: str
    engine: str | None
    language_code: str
    job_name: str
    error: str | None = None


class TranscriptionAdapter(Protocol):
    """Implementado por `LocalUnavailableTranscriptionAdapter` (dev/testes)
    e `AzureSpeechAdapter` (real)."""

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult: ...
