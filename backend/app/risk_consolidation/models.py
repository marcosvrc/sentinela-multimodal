"""Resultado consolidado de risco de uma analise.

Uma linha por `Analysis` (upsert em `consolidate_analysis_risk`). O
`risk_level`/`classification_label`/`outcome` vem SEMPRE do motor de regras
deterministico (`app.rules_engine`) - o LLM (`llm_*`) so contribui um texto
explicativo derivado; sua falha nunca apaga ou impede o resultado
deterministico ja calculado (`llm_status=FAILED` e `llm_summary=None`
convivem com um `risk_level` preenchido).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class RiskConsolidation(Base):
    __tablename__ = "risk_consolidations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=False, unique=True
    )

    outcome: Mapped[str] = mapped_column(String(20), nullable=False)  # MATCHED | INCONCLUSIVE
    risk_level: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("risk_levels.code"), nullable=True
    )
    classification_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    inconclusive_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    inconclusive_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Detalhe por code de regra avaliado - lista de
    # {code, outcome, risk_level, classification_label, inconclusive_reason}.
    code_evaluations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    llm_status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # SUCCESS | FAILED | SKIPPED
    llm_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_uncertainty_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    llm_output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
