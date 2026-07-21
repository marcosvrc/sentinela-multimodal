"""Configuracao tipada da aplicacao.

Configuracao centralizada, tipada, validada no startup, com separacao
entre valores publicos, internos e segredos. Falha rapido quando um campo
obrigatorio estiver ausente.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.enums import (
    LlmProvider,
    TranscriptionProvider,
    VisionProvider,
)


class Environment(str, Enum):
    LOCAL = "local"
    TEST = "test"
    HOMOLOGATION = "homologation"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Configuracao da API e dos workers.

    Valores sensiveis (chaves, segredos) nunca devem ter default neste
    arquivo; em producao vem de variaveis de ambiente injetadas pela
    plataforma de implantacao.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicacao ---
    app_name: str = "SentinelHealth API"
    environment: Environment = Environment.LOCAL
    api_version: str = "0.1.0"
    log_level: str = "INFO"

    # --- Banco de dados (obrigatorio, sem default em producao) ---
    database_url: PostgresDsn = Field(
        default="postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinelhealth"
    )

    # --- CORS ---
    # NoDecode: por padrao, pydantic-settings tenta decodificar campos
    # list[str] vindos de variavel de ambiente como JSON antes de rodar
    # qualquer field_validator - o que quebra o formato "a, b, c" usado no
    # .env. NoDecode entrega a string bruta para o validator abaixo tratar.
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # --- Armazenamento de midia (filesystem local) ---
    media_local_storage_root: str = "./.local-media"
    media_upload_url_ttl_seconds: int = 900
    # Segredo usado pelo adaptador LOCAL para assinar as URLs de upload
    # simuladas (HMAC).
    media_local_upload_secret: str = "dev-only-local-upload-secret-nao-usar-em-producao"

    # --- LLM de consolidacao ---
    # LOCAL (template deterministico, sem chamada de rede) por padrao; OPENAI
    # exige `openai_api_key`. Ver app/integrations/llm/.
    llm_provider: LlmProvider = LlmProvider.LOCAL

    # --- OpenAI (segredo real vem do Secrets Manager, nunca default) ---
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    # --- Transcricao de audio ---
    # LOCAL (sem motor de ASR, retorna UNAVAILABLE honesto) por padrao;
    # AZURE_SPEECH exige azure_speech_key/azure_speech_region. Ver
    # app/integrations/transcription/.
    transcription_provider: TranscriptionProvider = TranscriptionProvider.LOCAL

    # --- Azure Cognitive Services (segredo real nunca tem default -
    # dev local usa recursos criados via Azure CLI, ver
    # infra/environments/dev/README.md). Cada recurso tem key+endpoint/
    # regiao proprios porque sao servicos Cognitive Services
    # independentes. ---
    azure_speech_key: str | None = None
    azure_speech_region: str | None = None
    azure_vision_key: str | None = None
    azure_vision_endpoint: str | None = None
    azure_language_key: str | None = None
    azure_language_endpoint: str | None = None

    # --- Visao computacional de video ---
    # LOCAL (sem motor de pose/deteccao, retorna UNAVAILABLE honesto) por
    # padrao; OPENPOSE_YOLOV8 e o worker self-hosted (nao um servico
    # gerenciado de nuvem). `vision_max_sample_frames` limita quantos
    # quadros sao amostrados por video para manter a analise rapida em
    # CPU, usando amostras pequenas. Ver app/integrations/vision/.
    vision_provider: VisionProvider = VisionProvider.LOCAL
    vision_max_sample_frames: int = 8
    # Qual motor (YOLOv8/OpenPose) esta ligado dentro do adaptador
    # OPENPOSE_YOLOV8 e decidido pela tabela `feature_flags` (banco,
    # mutavel em runtime via `/admin/feature-flags`), nao por env - ver
    # `app.integrations.vision.get_vision_adapter` e
    # `app.feature_flags.models.FeatureFlags.vision_detection_enabled`/
    # `vision_pose_enabled`.

    # --- Identidade ---
    # Adaptador local unico: resolve o usuario a partir do cabecalho de
    # desenvolvimento `X-Dev-Subject` (ver `app.core.security`). Nao ha
    # provedor de identidade gerenciado em nuvem neste projeto.
    # Duracao de uma concessao break glass, usada como teto em
    # `app.api.routes.patients` (ver `min(data.duration_seconds, ...)`).
    session_max_age_seconds: int = 3600 * 8

    # --- Rate limiting ---
    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_auth: str = "10/minute"

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Retorna a configuracao (cacheada por processo)."""
    return Settings()
