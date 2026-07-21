"""Modelos de auditoria.

`AuditEvent` e append-only: nenhuma rota ou servico deve emitir UPDATE ou
DELETE sobre esta tabela. `AuditChainState` guarda o hash do ultimo evento
gravado, protegido por lock de linha (`SELECT ... FOR UPDATE`) durante a
gravacao para serializar concorrencia e manter a cadeia consistente mesmo
com escritas simultaneas (ver app.audit.service.record_event).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Preenchida pelo banco via IDENTITY ALWAYS (ver migration 0004); a
    # declaracao `Identity(always=True)` aqui e o que faz o SQLAlchemy
    # omitir a coluna do INSERT (em vez de enviar `NULL` explicitamente,
    # que o Postgres rejeita para colunas GENERATED ALWAYS).
    sequence: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), unique=True, nullable=False
    )
    schema_version: Mapped[int] = mapped_column(nullable=False, default=1)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    institution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)

    category: Mapped[str] = mapped_column(String(30), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)

    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    analysis_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    event_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditChainState(Base):
    """Linha singleton (id=1) com o hash do ultimo evento gravado."""

    __tablename__ = "audit_chain_state"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    last_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
