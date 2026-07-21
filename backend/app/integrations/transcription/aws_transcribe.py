"""Adaptador real de transcricao via Amazon Transcribe.

Uso do `boto3` encapsulado neste adaptador - o dominio
(`app.processors.audio`) so ve `TranscriptionAdapter` (Protocol). Segue o
fluxo batch padrao do Transcribe (Amazon Transcribe padrao, batch,
pt-BR):

1. `start_transcription_job` apontando para o objeto ja aprovado no bucket
   de midia (`s3://{media_bucket}/approved/{storage_key}` - o prefixo
   "approved/" e o mesmo usado por `S3StorageAdapter.promote()`, ver
   app/storage/s3.py), com o resultado gravado em
   `output_bucket`/`output_key`.
2. Poll de `get_transcription_job` ate `COMPLETED`/`FAILED`, com numero
   maximo de tentativas e intervalo fixo (limitacao MVP documentada
   abaixo).
3. Leitura do JSON de resultado do proprio `output_bucket` (nao da URL
   assinada temporaria que o Transcribe devolve, que expira e nao deveria
   ser logada/persistida) e extracao do texto plano da transcricao.

**Limitacao conhecida do MVP** (nao escondida): o poll e sincrono dentro da
mesma chamada do worker (`process_next_message`), adequado para arquivos
curtos de demonstracao. Producao com arquivos maiores deveria usar
notificacao assincrona (EventBridge/SNS na conclusao do job) em vez de
bloquear um worker - fora do escopo desta implementacao inicial, que
prioriza ter um adaptador real e correto sobre a arquitetura de polling
ideal.

**Nao exercitado contra a API real da AWS neste ambiente** (sem
credenciais/rede) - testado com um cliente `boto3` falso injetado
(`tests/test_transcription_aws_adapter.py`), verificando construcao da
requisicao e parsing da resposta.
"""

from __future__ import annotations

import json
import time
from typing import Any, Protocol

from app.core.enums import TranscriptionStatus
from app.integrations.transcription.base import TranscriptionRequest, TranscriptionResult
from app.storage.s3 import APPROVED_PREFIX


class _TranscribeClient(Protocol):
    def start_transcription_job(self, **kwargs: Any) -> dict: ...
    def get_transcription_job(self, **kwargs: Any) -> dict: ...


class _S3Client(Protocol):
    def get_object(self, **kwargs: Any) -> dict: ...


class AwsTranscribeAdapter:
    def __init__(
        self,
        *,
        transcribe_client: _TranscribeClient,
        s3_client: _S3Client,
        media_bucket: str,
        output_bucket: str,
        poll_interval_seconds: float = 5.0,
        max_poll_attempts: int = 60,
    ) -> None:
        self._transcribe = transcribe_client
        self._s3 = s3_client
        self._media_bucket = media_bucket
        self._output_bucket = output_bucket
        self._poll_interval_seconds = poll_interval_seconds
        self._max_poll_attempts = max_poll_attempts

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        output_key = f"transcriptions/{request.job_name}.json"
        # `request.storage_key` e a chave "nua" gravada no banco (sem
        # prefixo de area) - o prefixo "approved/" e detalhe interno de
        # `S3StorageAdapter` (app/storage/s3.py), adicionado aqui via a
        # mesma constante para nao duplicar a string literal em dois
        # modulos. O objeto so existe em s3://{media_bucket}/approved/...
        # depois de `promote()`, nunca em quarantine/.
        media_object_key = APPROVED_PREFIX + request.storage_key

        try:
            self._transcribe.start_transcription_job(
                TranscriptionJobName=request.job_name,
                LanguageCode=request.language_code,
                MediaFormat=request.media_format,
                Media={"MediaFileUri": f"s3://{self._media_bucket}/{media_object_key}"},
                OutputBucketName=self._output_bucket,
                OutputKey=output_key,
            )
        except Exception as exc:  # noqa: BLE001 - erro de fornecedor nunca propaga cru
            return self._failed_result(request, f"Falha ao iniciar job: {exc}")

        job_status = None
        for _ in range(self._max_poll_attempts):
            try:
                response = self._transcribe.get_transcription_job(
                    TranscriptionJobName=request.job_name
                )
            except Exception as exc:  # noqa: BLE001
                return self._failed_result(request, f"Falha ao consultar job: {exc}")

            job_status = response["TranscriptionJob"]["TranscriptionJobStatus"]
            if job_status in ("COMPLETED", "FAILED"):
                break
            time.sleep(self._poll_interval_seconds)

        if job_status != "COMPLETED":
            reason = "timeout aguardando conclusao" if job_status is None else job_status
            return self._failed_result(request, f"Job de transcricao nao concluido: {reason}")

        try:
            output_object = self._s3.get_object(Bucket=self._output_bucket, Key=output_key)
            payload = json.loads(output_object["Body"].read())
            transcript_text = payload["results"]["transcripts"][0]["transcript"]
        except Exception as exc:  # noqa: BLE001
            return self._failed_result(request, f"Falha ao ler resultado da transcricao: {exc}")

        return TranscriptionResult(
            status=TranscriptionStatus.COMPLETED,
            transcript_text=transcript_text,
            provider="aws_transcribe",
            engine="aws-transcribe-standard-batch",
            language_code=request.language_code,
            job_name=request.job_name,
        )

    def _failed_result(
        self, request: TranscriptionRequest, error: str
    ) -> TranscriptionResult:
        return TranscriptionResult(
            status=TranscriptionStatus.FAILED,
            transcript_text=None,
            provider="aws_transcribe",
            engine="aws-transcribe-standard-batch",
            language_code=request.language_code,
            job_name=request.job_name,
            error=error[:500],
        )
