"""Contratos do relatorio de analise."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ReportRead(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    state: str
    content: dict
    pdf_sha256: str | None
    pdf_generated_at: datetime | None
    confirmed_by: str | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
