"""Contratos do modulo de auditoria."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.enums import AuditCategory, AuditResult


class AuditEventRead(BaseModel):
    id: uuid.UUID
    sequence: int
    occurred_at: datetime
    actor: str
    actor_role: str | None
    unit: str | None
    category: AuditCategory
    action: str
    resource_type: str
    resource_id: str | None
    result: AuditResult
    justification: str | None
    request_id: str | None
    analysis_id: str | None
    workflow_id: str | None
    job_id: str | None
    # Detalhe completo da acao (payload especifico de cada `action`, ex.:
    # modelo/provider/hash de entrada-saida de uma chamada de IA, filtros
    # de uma consulta, resultado por modalidade de um processamento) -
    # exibido na UI via popup dedicado (ver `AuditPage.tsx`), nunca editado
    # (a tabela e append-only). `event_hash`/`prev_hash` tambem expostos
    # aqui para permitir a mesma verificacao visual da cadeia de
    # integridade que `app.audit.hashing.verify_chain` faz
    # programaticamente.
    event_metadata: dict
    event_hash: str
    prev_hash: str | None

    model_config = {"from_attributes": True}
