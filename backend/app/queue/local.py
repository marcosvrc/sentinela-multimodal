"""Adaptador de fila local (dev/testes), backeado por tabela PostgreSQL.

TEMPORARIO no mesmo sentido dos demais adaptadores locais (identidade,
storage): substitui o Amazon SQS real durante o desenvolvimento. Usa uma
tabela em vez de fila em memoria de processo porque workers sao stateless
por design (estado e artefatos permanecem em PostgreSQL/S3, nunca em
memoria do worker) e o dev precisa poder reiniciar a API/worker sem perder
mensagens em transito.

`SELECT ... FOR UPDATE SKIP LOCKED` evita que dois workers concorrentes
peguem a mesma mensagem (equivalente ao "visibility timeout" do SQS, aqui
implementado como uma janela de tempo em `visible_at`).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import SessionLocal
from app.queue.base import QueueMessage
from app.queue.models import QueueMessageRecord


class LocalDbQueueAdapter:
    def __init__(self, *, visibility_timeout_seconds: int = 300):
        self._visibility_timeout_seconds = visibility_timeout_seconds

    def enqueue(self, body: dict) -> None:
        session = SessionLocal()
        try:
            session.add(QueueMessageRecord(body=body, status="PENDING"))
            session.commit()
        finally:
            session.close()

    def receive(self, max_messages: int = 1) -> list[QueueMessage]:
        session = SessionLocal()
        try:
            now = datetime.now(tz=timezone.utc)
            rows = session.scalars(
                select(QueueMessageRecord)
                .where(
                    (QueueMessageRecord.status == "PENDING")
                    | (
                        (QueueMessageRecord.status == "IN_FLIGHT")
                        & (QueueMessageRecord.visible_at <= now)
                    )
                )
                .order_by(QueueMessageRecord.created_at)
                .limit(max_messages)
                .with_for_update(skip_locked=True)
            ).all()

            messages: list[QueueMessage] = []
            for row in rows:
                receipt_handle = secrets.token_urlsafe(24)
                row.status = "IN_FLIGHT"
                row.receipt_handle = receipt_handle
                row.visible_at = now + timedelta(seconds=self._visibility_timeout_seconds)
                messages.append(QueueMessage(receipt_handle=receipt_handle, body=row.body))

            session.commit()
            return messages
        finally:
            session.close()

    def delete(self, receipt_handle: str) -> None:
        session = SessionLocal()
        try:
            row = session.scalar(
                select(QueueMessageRecord).where(
                    QueueMessageRecord.receipt_handle == receipt_handle
                )
            )
            if row is not None:
                session.delete(row)
                session.commit()
        finally:
            session.close()
