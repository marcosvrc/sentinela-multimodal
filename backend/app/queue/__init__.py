"""Selecao do adaptador de fila por configuracao (mesmo padrao de app/storage)."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.enums import StorageBackend
from app.queue.base import QueueAdapter
from app.queue.local import LocalDbQueueAdapter


@lru_cache
def get_queue_adapter() -> QueueAdapter:
    settings = get_settings()

    # Reaproveita `media_storage_backend` (LOCAL/S3) como interruptor
    # LOCAL/AWS tambem para a fila: no scaffold atual, dev sempre usa os
    # dois adaptadores locais juntos, e producao sempre usa os dois AWS
    # juntos. Se um dia divergirem (ex: S3 real com fila local), trocar por
    # uma configuracao dedicada `queue_backend` sera uma mudanca isolada
    # aqui.
    if settings.media_storage_backend is StorageBackend.LOCAL:
        return LocalDbQueueAdapter()

    if not settings.sqs_analysis_queue_url:
        raise RuntimeError("Fila SQS selecionada mas SQS_ANALYSIS_QUEUE_URL nao configurada.")

    from app.queue.sqs import SqsQueueAdapter

    return SqsQueueAdapter(queue_url=settings.sqs_analysis_queue_url, region=settings.aws_region)
