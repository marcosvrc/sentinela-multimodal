"""Testes do adaptador de fila local (tabela PostgreSQL).

Precisa de Postgres real; pulado automaticamente quando indisponivel neste
sandbox (roda no CI).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal
from app.queue.local import LocalDbQueueAdapter


def _db_available() -> bool:
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        session.close()


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres indisponivel neste ambiente")


@pytest.fixture(autouse=True)
def _clean_queue_table():
    session = SessionLocal()
    try:
        session.execute(text("DELETE FROM analysis_queue_messages"))
        session.commit()
    finally:
        session.close()
    yield


def test_enqueue_and_receive() -> None:
    adapter = LocalDbQueueAdapter()
    adapter.enqueue({"analysis_id": "abc-123"})

    messages = adapter.receive(max_messages=1)
    assert len(messages) == 1
    assert messages[0].body == {"analysis_id": "abc-123"}


def test_received_message_is_not_returned_again_before_visibility_timeout_expires() -> None:
    adapter = LocalDbQueueAdapter(visibility_timeout_seconds=300)
    adapter.enqueue({"analysis_id": "abc-123"})

    first = adapter.receive(max_messages=1)
    assert len(first) == 1

    second = adapter.receive(max_messages=1)
    assert second == []


def test_delete_removes_message() -> None:
    adapter = LocalDbQueueAdapter()
    adapter.enqueue({"analysis_id": "abc-123"})

    [message] = adapter.receive(max_messages=1)
    adapter.delete(message.receipt_handle)

    session = SessionLocal()
    try:
        count = session.execute(text("SELECT COUNT(*) FROM analysis_queue_messages")).scalar()
        assert count == 0
    finally:
        session.close()


def test_delete_is_idempotent_for_unknown_handle() -> None:
    adapter = LocalDbQueueAdapter()
    # Nao deve lancar excecao mesmo para um receipt_handle inexistente
    # (mesma semantica idempotente do SQS real).
    adapter.delete("does-not-exist")


def test_receive_respects_fifo_order() -> None:
    adapter = LocalDbQueueAdapter()
    adapter.enqueue({"order": 1})
    adapter.enqueue({"order": 2})

    messages = adapter.receive(max_messages=2)
    assert [message.body["order"] for message in messages] == [1, 2]
