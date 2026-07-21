"""Contratos de observacao clinica."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import ObservationReadingQuality, ObservationType


class ObservationCreate(BaseModel):
    """Corpo de POST /patients/{patient_id}/observations.

    `value` acomoda tipos simples (`{"value": 98}`) e compostos
    (`{"systolic": 120, "diastolic": 80}`); `context` carrega campos
    condicionais como os exigidos para glicemia (momento, tipo de
    paciente, uso de insulina).
    """

    observation_type: ObservationType
    value: dict = Field(..., description="Forma depende do tipo; ver app.observations.validation")
    unit: str | None = None
    context: dict = Field(default_factory=dict)
    measured_at: datetime
    origin: str = Field(..., min_length=1, max_length=100)
    author: str = Field(..., min_length=1, max_length=200)
    method: str | None = None
    reading_quality: ObservationReadingQuality = ObservationReadingQuality.VALID


class ObservationRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    observation_type: ObservationType
    value: dict
    unit: str | None
    context: dict
    measured_at: datetime
    origin: str
    author: str
    method: str | None
    reading_quality: ObservationReadingQuality
    created_at: datetime

    model_config = {"from_attributes": True}
