"""Contratos de submissao/estado da analise (item 10)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.enums import ModalityType


class AnalysisModalityStateRead(BaseModel):
    id: uuid.UUID
    modality_type: ModalityType
    # Vincula o estado de processamento ao arquivo especifico que o
    # originou (uma analise pode ter mais de uma midia da mesma
    # modalidade - ver app.orchestrator.service.submit_analysis); `None`
    # apenas para o estado sintetico `TEXT` (nao vem de upload).
    media_asset_id: uuid.UUID | None
    status: str
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
