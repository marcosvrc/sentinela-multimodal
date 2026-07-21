"""Achado por modalidade.

Uma linha por `AnalysisModalityState` processado com sucesso. Achados de
`nature` `ORIGINAL_DATA` vem de processadores que extraem fatos estruturais
do proprio dado (dimensao, duracao, contagem de palavras), sem inferencia
de IA; `MODEL_OBSERVATION`/`ASSISTED_HYPOTHESIS` vem de integracoes com
LLM/Transcribe/visao computacional.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class ModalityFinding(Base):
    __tablename__ = "modality_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=False
    )
    modality_state_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_modality_states.id"), nullable=False
    )
    modality_type: Mapped[str] = mapped_column(String(20), nullable=False)
    nature: Mapped[str] = mapped_column(String(40), nullable=False)
    quality_state: Mapped[str] = mapped_column(String(20), nullable=False)
    quality_metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    quality_factors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
