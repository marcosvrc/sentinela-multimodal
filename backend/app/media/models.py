"""Modelos de analise e midia.

Este modulo cobre apenas o suficiente para criar uma analise, emitir URLs
de upload por modalidade e levar o objeto de "aguardando upload" ate
"aprovado"/"rejeitado" na quarentena. A maquina de estados completa da
analise (QUEUED em diante), o processamento por modalidade e o motor de
regras sao implementados em outros modulos.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="CREATED")
    # Campo texto adicional opcional - nao passa por upload/quarentena, e
    # gravado diretamente aqui.
    additional_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Entradas clinicas estruturadas ja conhecidas no momento da criacao da
    # analise (consumidas pelo Consolidador de Risco), chaveadas pelo `code`
    # do conjunto de regras (ex: {"spo2": {"spo2_percent": 91, ...}}). NAO e
    # extraido automaticamente de audio/video/imagem - essa extracao de
    # conteudo (transcricao, visao computacional) e feita separadamente;
    # aqui o profissional informa o que ja mediu, e o consolidador
    # (app.risk_consolidation) executa o motor de regras sobre isso.
    structured_clinical_inputs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("institutions.id"), nullable=False
    )
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id"), nullable=False
    )
    modality_type: Mapped[str] = mapped_column(String(20), nullable=False)
    upload_state: Mapped[str] = mapped_column(String(20), nullable=False, default="AWAITING_UPLOAD")

    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    declared_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    detected_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actual_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
