"""Modelo de observacao clinica.

O valor e o contexto ficam em colunas JSONB para acomodar tipos compostos
(pressao arterial) e campos condicionais (glicemia) sem exigir uma coluna
por tipo de observacao ou uma migration a cada novo campo de contexto.
`app.observations.validation` garante a forma correta de cada tipo antes
da escrita.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class ClinicalObservation(Base):
    __tablename__ = "clinical_observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    observation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    origin: Mapped[str] = mapped_column(String(100), nullable=False)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reading_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="VALID")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
