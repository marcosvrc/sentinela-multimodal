"""Contratos de analise e upload de midia."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import MediaUploadState, ModalityType


class AnalysisCreate(BaseModel):
    patient_id: uuid.UUID
    additional_text: str | None = Field(default=None, max_length=10_000)
    # Entradas clinicas ja conhecidas (ex: {"spo2": {"spo2_percent": 91}}),
    # usadas pelo consolidador de risco - ver Analysis.structured_clinical_inputs.
    structured_clinical_inputs: dict[str, dict] = Field(default_factory=dict)


class AnalysisRead(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    status: str
    additional_text: str | None
    structured_clinical_inputs: dict
    created_by: str
    # Nome completo do profissional, resolvido a partir de `created_by`
    # (external_subject) via `identity.User` - `None` apenas se o usuario
    # que criou a analise nao existir mais no espelho local (nao deveria
    # acontecer em uso normal, mas evita quebrar a listagem).
    created_by_full_name: str | None = None
    # Dados do paciente vinculado, resolvidos via `Patient` (id fixo em
    # `patient_id` acima) - usados na coluna/filtro de paciente do
    # historico de analises. `None` apenas se o paciente nao existir mais
    # (nao deveria acontecer em uso normal).
    patient_full_name: str | None = None
    patient_medical_record_number: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MediaUploadRequest(BaseModel):
    modality_type: ModalityType
    filename: str = Field(..., min_length=1, max_length=255)
    mime_type: str = Field(..., min_length=1, max_length=100)
    size_bytes: int = Field(..., gt=0)


class MediaUploadResponse(BaseModel):
    media_id: uuid.UUID
    upload_url: str
    upload_method: str
    upload_headers: dict[str, str]
    expires_at: datetime


class MediaConfirmRequest(BaseModel):
    checksum_sha256: str = Field(..., min_length=64, max_length=64)


class ProfessionalRead(BaseModel):
    """Item do filtro "Medico" do historico de analises e do campo
    pesquisavel de funcionario no registro de observacao clinica.
    `external_subject` e o
    mesmo valor gravado em `Analysis.created_by`, usado como valor do
    filtro. `registration_number` vem do cadastro de funcionario
    (`app.administration.models.Employee`) vinculado a este usuario, para
    exibir "matricula - nome"; fica `None` quando o usuario nao tem um
    funcionario administrativo vinculado (caso legado/de teste)."""

    external_subject: str
    full_name: str
    registration_number: str | None = None


class AnalysisStatsRead(BaseModel):
    """Estatisticas agregadas de todas as analises JA CONSOLIDADAS
    (com `RiskConsolidation` gravada) da instituicao do usuario logado -
    alimenta os "big numbers" da tela de revisao da analise, dando
    contexto de quao frequentemente o motor de regras consegue classificar (`MATCHED`)
    versus fica inconclusivo, entre todas as analises ja processadas.
    Nao e uma metrica de acuracia clinica validada contra um "gabarito" -
    e a proporcao de analises com resultado conclusivo (`MATCHED`) sobre o
    total de analises consolidadas."""

    total_analyses_consolidated: int
    conclusive_count: int
    conclusive_rate_percent: float


class MediaAssetRead(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    modality_type: ModalityType
    upload_state: MediaUploadState
    original_filename: str
    declared_mime_type: str
    declared_size_bytes: int
    detected_mime_type: str | None
    actual_size_bytes: int | None
    checksum_sha256: str | None
    rejection_reason: str | None
    created_at: datetime
    confirmed_at: datetime | None

    model_config = {"from_attributes": True}
