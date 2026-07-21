"""Contrato da tela de feature flags (`/admin/feature-flags`, acesso
restrito a administrador - ver `app.feature_flags`).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import LlmProvider


class ModelOption(BaseModel):
    """Uma opcao de modelo selecionavel na tela - lista curada (nao uma
    chamada dinamica ao provedor, que exigiria a credencial configurada
    so para listar modelos)."""

    value: str
    label: str


# Lista curada de modelos OpenAI disponiveis para consolidacao de risco/
# apoio a analise clinica (chat completions com JSON schema estrito - ver
# app.integrations.llm.openai_adapter). Atualizar manualmente conforme a
# OpenAI descontinuar/lancar modelos; nao ha endpoint de "listar modelos
# compativeis com json_schema strict" na API da OpenAI.
OPENAI_MODEL_OPTIONS: tuple[ModelOption, ...] = (
    ModelOption(value="gpt-4o-mini", label="GPT-4o mini (recomendado - custo baixo)"),
    ModelOption(value="gpt-4o", label="GPT-4o"),
    ModelOption(value="gpt-4.1", label="GPT-4.1"),
    ModelOption(value="gpt-4.1-mini", label="GPT-4.1 mini"),
)

# Lista curada de modelos Gemini - apenas para PLANEJAMENTO (ver
# app.integrations.llm.gemini_adapter): nao ha adaptador real ainda,
# selecionar Gemini como provedor falha explicitamente ao chamar o LLM.
GEMINI_MODEL_OPTIONS: tuple[ModelOption, ...] = (
    ModelOption(value="gemini-1.5-flash", label="Gemini 1.5 Flash"),
    ModelOption(value="gemini-1.5-pro", label="Gemini 1.5 Pro"),
    ModelOption(value="gemini-2.0-flash", label="Gemini 2.0 Flash"),
)


class FeatureFlagsRead(BaseModel):
    llm_provider_enabled: bool
    llm_provider: LlmProvider
    llm_openai_model: str
    llm_gemini_model: str
    modality_audio_enabled: bool
    modality_video_enabled: bool
    modality_image_enabled: bool
    vision_detection_enabled: bool
    vision_pose_enabled: bool
    image_recognition_enabled: bool
    sentiment_analysis_enabled: bool
    auto_clinical_support_enabled: bool
    updated_at: datetime
    updated_by: str | None

    # Listas de opcoes embutidas na propria resposta (nao um endpoint
    # separado) para a tela nao precisar de uma segunda chamada so para
    # saber quais modelos oferecer nos selects.
    openai_model_options: tuple[ModelOption, ...] = Field(default=OPENAI_MODEL_OPTIONS)
    gemini_model_options: tuple[ModelOption, ...] = Field(default=GEMINI_MODEL_OPTIONS)
    # Documenta explicitamente na resposta que Gemini ainda nao tem
    # integracao real - a tela usa este campo para exibir um aviso, em vez
    # de descobrir isso so quando uma chamada real falhar.
    gemini_implemented: bool = Field(default=False)

    model_config = {"from_attributes": True}


class FeatureFlagsUpdate(BaseModel):
    """Todos os campos opcionais - a rota PATCH so altera o que for
    enviado (mesmo padrao de `MedicalSpecialtyUpdate`/`CareUnitUpdate`)."""

    llm_provider_enabled: bool | None = None
    llm_provider: LlmProvider | None = None
    llm_openai_model: str | None = Field(default=None, min_length=1, max_length=100)
    llm_gemini_model: str | None = Field(default=None, min_length=1, max_length=100)
    modality_audio_enabled: bool | None = None
    modality_video_enabled: bool | None = None
    modality_image_enabled: bool | None = None
    vision_detection_enabled: bool | None = None
    vision_pose_enabled: bool | None = None
    image_recognition_enabled: bool | None = None
    sentiment_analysis_enabled: bool | None = None
    auto_clinical_support_enabled: bool | None = None
