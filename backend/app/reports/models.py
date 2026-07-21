"""Relatorio de uma analise.

Uma linha por `Analysis` (upsert em `generate_report`, mesmo padrao de
`app.risk_consolidation.models.RiskConsolidation`). `content` e o dict
estruturado montado por `app.reports.builder`; o PDF NAO fica em `content`
(binario grande) - fica em `pdf_storage_key`, gravado via
`StorageAdapter.write_generated_object` somente no momento da confirmacao
(`state=CONFIRMED`), para que o PDF baixado corresponda exatamente ao
relatorio que o profissional revisou e confirmou.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=False, unique=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )

    state: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Ultimo resultado do botao "Analisar dados clinicos" (apoio a analise
    # clinica assistido por LLM, `app.clinical_support.service.
    # generate_analysis_clinical_support_summary`) - sob demanda, cada
    # geracao nova SOBRESCREVE esta coluna. `None` se o profissional nunca
    # clicou no botao para esta analise. Persistido (em vez de so exibido
    # ad-hoc na tela) para que o PDF exportado (gerado a partir de
    # `content`, montado com este campo em `app.reports.service.
    # _build_content`) reflita o ultimo apoio gerado antes da confirmacao.
    clinical_support_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    pdf_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pdf_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    confirmed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
