"""Estado de processamento por modalidade dentro de uma analise (item 10).

Criado quando a analise e submetida (`app.orchestrator.service.submit_analysis`):
uma linha por modalidade com conteudo aprovado (midia `APPROVED`) ou por
`TEXT` quando `Analysis.additional_text` estiver preenchido. O processador
real de cada modalidade (item 11, `app.processors.registry`) atualiza
`status`/`error_message`; quando nenhum processador esta registrado para a
modalidade, o orquestrador (item 10) marca `FAILED_RETRYABLE` por falta de
processador - ver `app.orchestrator.worker`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class AnalysisModalityState(Base):
    __tablename__ = "analysis_modality_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=False
    )
    modality_type: Mapped[str] = mapped_column(String(20), nullable=False)
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("media_assets.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
