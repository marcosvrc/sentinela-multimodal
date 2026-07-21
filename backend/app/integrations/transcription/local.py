"""Adaptador LOCAL de transcricao: honesto sobre nao ter motor de ASR.

TEMPORARIO (mesmo padrao dos demais adaptadores locais - storage, fila,
identidade, LLM): usado em dev/testes. Diferente do adaptador LOCAL de LLM
(que produz um resumo deterministico real via template), este NAO pode
produzir uma transcricao real - reconhecimento de fala exige um motor de
ASR (Azure AI Speech ou um modelo local equivalente) que este ambiente
nao tem. Retornar uma transcricao fabricada seria pior que nao transcrever
(violaria o principio "nunca fingir" usado em todo o projeto - ex.: secoes
6/7 do laudo so sao preenchidas quando ha achado real). Por isso este
adaptador sempre retorna `TranscriptionStatus.UNAVAILABLE`, nunca
`COMPLETED`.
"""

from __future__ import annotations

from app.core.enums import TranscriptionStatus
from app.integrations.transcription.base import TranscriptionRequest, TranscriptionResult


class LocalUnavailableTranscriptionAdapter:
    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        return TranscriptionResult(
            status=TranscriptionStatus.UNAVAILABLE,
            transcript_text=None,
            provider="local",
            engine=None,
            language_code=request.language_code,
            job_name=request.job_name,
            error=(
                "Adaptador LOCAL nao inclui motor de reconhecimento de fala (ASR). "
                "Transcricao real requer TRANSCRIPTION_PROVIDER=AZURE_SPEECH."
            ),
        )
