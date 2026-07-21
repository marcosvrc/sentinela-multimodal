"""Interface de fila de processamento assincrono.

Duas implementacoes, mesmo padrao do adaptador de storage
(app/storage/base.py): `LocalDbQueueAdapter` (dev/testes, tabela PostgreSQL)
e `SqsQueueAdapter` (homologacao/producao, Amazon SQS). As mensagens
carregam apenas identificadores e metadados minimos, nunca midia ou
resultado clinico - o worker que consome a mensagem busca o conteudo
completo direto do banco/storage antes de processar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class QueueMessage:
    """Uma mensagem recebida da fila, pronta para ser processada ou apagada."""

    receipt_handle: str
    body: dict


class QueueAdapter(Protocol):
    def enqueue(self, body: dict) -> None: ...

    def receive(self, max_messages: int = 1) -> list[QueueMessage]: ...

    def delete(self, receipt_handle: str) -> None: ...
