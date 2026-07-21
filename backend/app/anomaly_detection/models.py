"""Modelo de alerta de anomalia.

`ClinicalAlert` e independente de `RiskConsolidation`: nunca alimenta nem
altera a classificacao de risco do motor de regras deterministico - e um
fluxo consultivo paralelo de monitoramento preventivo sobre a serie
temporal de observacoes clinicas do paciente.

Cada alerta deve conter severidade, evidencia, horario, paciente,
regra/modelo de origem, confianca quando aplicavel e acao esperada. O
fluxo registra reconhecimento, responsavel, tempo de resposta,
escalonamento e encerramento.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class ClinicalAlert(Base):
    __tablename__ = "clinical_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    # Observacao que disparou o alerta - nulavel apenas por robustez de
    # schema; toda criacao real sempre preenche (ver
    # `app.anomaly_detection.service.evaluate_and_create_alerts`).
    observation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clinical_observations.id"), nullable=True
    )
    signal_key: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    # Identifica a versao do detector que gerou o alerta - mesmo principio
    # de rastreabilidade de `ClinicalRuleSet.version`/`RiskConsolidation`:
    # modelo e versao devem ser sempre rastreaveis.
    detector_source: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expected_action: Mapped[str] = mapped_column(Text, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    acknowledged_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    escalated_to: Mapped[str | None] = mapped_column(String(200), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    resolved_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
