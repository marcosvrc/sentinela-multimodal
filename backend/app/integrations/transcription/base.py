"""Contrato do adaptador de transcricao de audio.

Mesmo padrao arquitetural do adaptador de LLM (`app.integrations.llm.base`):
o dominio (`app.processors.audio`) depende apenas deste Protocol, nunca de
`boto3`/`httpx` diretamente - nenhum modulo de dominio importa diretamente
boto3 ou tipos especificos da AWS. `TranscriptionRequest` carrega
`storage_key` para o adaptador
AWS (que referencia o objeto diretamente no S3, sem reenviar bytes) e,
opcionalmente, `audio_bytes` para adaptadores sem integracao nativa de
storage do provedor (Azure AI Speech - Fast Transcription API recebe o
arquivo direto no corpo da requisicao) - o processador
(`app.processors.audio`) ja le os bytes do storage aprovado para a analise
acustica local, entao reaproveita-los aqui nao adiciona nenhuma leitura
extra."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.enums import TranscriptionStatus


@dataclass(frozen=True)
class TranscriptionRequest:
    """Referencia ao objeto de audio ja aprovado, mais os bytes quando o
    provedor exigir upload direto (`audio_bytes`, usado apenas pelo
    adaptador Azure - o adaptador AWS ignora este campo e usa somente
    `storage_key`)."""

    storage_key: str
    language_code: str
    media_format: str  # "wav" | "mp3" | "mp4" (extensao esperada pelo Transcribe)
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
    e `AwsTranscribeAdapter` (real)."""

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult: ...
