"""Contratos de criacao e acompanhamento de analise.

Estes schemas sao definidos antes da implementacao dos endpoints:
contratos fundamentais precedem os modulos funcionais. A implementacao
real dos endpoints de analysis_jobs consome estes mesmos schemas, sem
redefini-los.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import AnalysisAction, AnalysisStatus, ModalityStatus, ModalityType


class RequiredUpload(BaseModel):
    """Uma URL pre-assinada que o frontend deve usar para enviar uma midia."""

    media_id: str
    modality: ModalityType
    upload_url: str
    expires_at: datetime
    required_headers: dict[str, str] = Field(default_factory=dict)


class AnalysisCreateResponse(BaseModel):
    """Resposta de POST /analyses: retorna o identificador da analise e
    as URLs pre-assinadas de upload necessarias para cada midia."""

    analysis_id: str
    status: AnalysisStatus
    required_uploads: list[RequiredUpload]


class ModalityStatusItem(BaseModel):
    type: ModalityType
    status: ModalityStatus


class AnalysisStatusResponse(BaseModel):
    """Resposta de GET /analyses/{id} consumida pelo polling do frontend.

    `available_actions` e sempre calculado pelo backend; o frontend nao
    deduz transicoes permitidas (ver ANALYSIS_STATUS_TRANSITIONS).
    """

    analysis_id: str
    status: AnalysisStatus
    created_at: datetime
    updated_at: datetime
    modalities: list[ModalityStatusItem]
    available_actions: list[AnalysisAction]
