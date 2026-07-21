"""Contratos de cadastro de paciente."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class PatientCreate(BaseModel):
    """Corpo de POST /patients.

    A idade nunca e recebida nem armazenada: e sempre derivada de
    `birth_date`. `height_cm` e opcional (permite
    completar o cadastro sem a medida em maos e preencher depois via
    PATCH) - faixa fisiologicamente possivel de adulto/adolescente
    (30-272 cm, mesmo limite usado por `ObservationType.HEIGHT` em
    `app.observations.validation`, para manter as duas fontes de altura
    consistentes).
    """

    medical_record_number: str = Field(..., min_length=1, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=200)
    birth_date: date
    registered_sex: str = Field(..., min_length=1, max_length=30)
    email: EmailStr | None = None
    height_cm: float | None = Field(default=None, ge=30, le=272)

    @field_validator("birth_date")
    @classmethod
    def _birth_date_not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Data de nascimento nao pode ser no futuro.")
        return value


class PatientUpdate(BaseModel):
    """Corpo de PATCH /patients/{patient_id}. Todos os campos sao opcionais
    (semantica de patch parcial - so os informados sao alterados); a tela
    de edicao sempre envia o registro completo apos carregar os dados
    atuais, mas a API aceita atualizacoes parciais (ex.: apenas
    reativar/desativar) para os demais fluxos administrativos."""

    medical_record_number: str | None = Field(default=None, min_length=1, max_length=100)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    birth_date: date | None = None
    registered_sex: str | None = Field(default=None, min_length=1, max_length=30)
    email: EmailStr | None = None
    height_cm: float | None = Field(default=None, ge=30, le=272)
    active: bool | None = None

    @field_validator("birth_date")
    @classmethod
    def _birth_date_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Data de nascimento nao pode ser no futuro.")
        return value


class PatientRead(BaseModel):
    id: uuid.UUID
    medical_record_number: str
    full_name: str
    birth_date: date
    age: int
    registered_sex: str
    email: str | None
    height_cm: float | None
    active: bool
    # Se o paciente tem ao menos uma `Analysis` registrada (qualquer
    # estado) - decide se o icone de atalho para o historico de analises
    # aparece na listagem de pacientes.
    has_analyses: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BreakGlassRequest(BaseModel):
    """Solicitacao de acesso de emergencia.

    Sempre exige justificativa nao vazia; `duration_seconds` e limitado a
    no maximo 4 horas para nao se tornar um vinculo assistencial informal.
    """

    justification: str = Field(..., min_length=10, max_length=2000)
    duration_seconds: int = Field(default=3600, ge=60, le=4 * 3600)


class BreakGlassGrantRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    justification: str
    granted_at: datetime
    expires_at: datetime
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class CareUnitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class CareUnitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    active: bool | None = None


class CareUnitRead(BaseModel):
    id: uuid.UUID
    name: str
    active: bool

    model_config = {"from_attributes": True}


class PatientCareAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    care_unit_id: uuid.UUID | None = None


class PatientCareAssignmentRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    user_id: uuid.UUID
    care_unit_id: uuid.UUID | None
    active: bool
    assigned_by: str
    assigned_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}
