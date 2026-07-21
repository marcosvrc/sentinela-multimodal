"""Contratos de alerta de anomalia."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import AlertSeverity, AlertStatus


class ClinicalAlertRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    observation_id: uuid.UUID | None
    signal_key: str
    severity: AlertSeverity
    status: AlertStatus
    detector_source: str
    confidence: float | None
    evidence: dict
    expected_action: str
    detected_at: datetime

    acknowledged_by: str | None
    acknowledged_at: datetime | None
    escalated_to: str | None
    escalated_at: datetime | None
    escalation_reason: str | None
    resolved_by: str | None
    resolved_at: datetime | None
    resolution_notes: str | None

    created_at: datetime

    model_config = {"from_attributes": True}


class AlertSeverityCounts(BaseModel):
    """Quantidade de alertas por severidade para um paciente, usada nos
    "big numbers" do painel de alertas da tela de paciente. Conta todos
    os status (aberto, reconhecido, escalado, encerrado); o filtro por
    status continua disponivel na listagem detalhada apos escolher uma
    severidade."""

    critical: int = 0
    high: int = 0
    moderate: int = 0


class EscalateAlertRequest(BaseModel):
    escalated_to: str = Field(..., min_length=1, max_length=200)
    reason: str = Field(..., min_length=10, max_length=2000)


class ResolveAlertRequest(BaseModel):
    notes: str = Field(..., min_length=10, max_length=2000)
