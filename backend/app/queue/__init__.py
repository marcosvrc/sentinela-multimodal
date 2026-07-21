"""Selecao do adaptador de fila (mesmo padrao de app/storage)."""

from __future__ import annotations

from functools import lru_cache

from app.queue.base import QueueAdapter
from app.queue.local import LocalDbQueueAdapter


@lru_cache
def get_queue_adapter() -> QueueAdapter:
    return LocalDbQueueAdapter()
