"""Configuracao de feature flags de IA/multimodalidade, mutavel em runtime
via tela de administracao (`/admin/feature-flags`, acesso restrito a
administrador).

Linha singleton (id=1, mesmo padrao de `app.audit.models.AuditChainState`)
- nao ha um flag por instituicao neste MVP porque os providers de LLM/
visao computacional sao infraestrutura do PROCESSO (credenciais, modelos
instalados no worker), nao um dado clinico por tenant. A linha e seedada
pela propria migration (0018), nunca criada de forma lazy em codigo, para
que `select(...).where(id==1)` nunca precise tratar "linha ausente" como
caso valido.

Diferente de `Settings` (env, lido uma unica vez no boot e cacheado via
`lru_cache` em `app.core.config.get_settings`), esta tabela e consultada a
cada chamada de `get_llm_adapter`/`get_vision_adapter` (sem cache de
processo) - e o que permite ligar/desligar um provider sem reiniciar a
API/worker.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_base import Base


class FeatureFlags(Base):
    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)

    # --- LLM (consolidacao de risco + apoio a analise clinica) ---
    # `llm_provider_enabled` e o interruptor geral: quando `false`, o
    # sistema roda no adaptador LOCAL (template deterministico, sem
    # chamada de rede) independente do que `llm_provider` diga - mesmo
    # principio de fail-safe usado em `Settings.requires_real_identity_
    # provider`. Quando `true`, `llm_provider` decide OPENAI ou GEMINI.
    # Default `False` segue a mesma convencao "seguro por padrao" de
    # `LLM_PROVIDER=LOCAL`/`VISION_PROVIDER=LOCAL`/`TRANSCRIPTION_
    # PROVIDER=LOCAL` do restante do projeto - ligar um provider real e
    # sempre uma acao explicita do administrador na tela de feature flags,
    # nunca o padrao herdado silenciosamente.
    llm_provider_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="OPENAI")
    llm_openai_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="gpt-4o-mini"
    )
    # Amazon Bedrock (ver app.integrations.llm.bedrock_adapter) - usa as
    # credenciais IAM do processo (mesmo padrao de S3/SQS/Transcribe/
    # Rekognition), nunca uma chave de API externa. `model_id` e o ID
    # completo do modelo no Bedrock (ex.: "anthropic.claude-3-5-sonnet-
    # 20241022-v2:0" ou um inference profile "us.anthropic...").
    llm_bedrock_model: Mapped[str] = mapped_column(
        String(200), nullable=False, default="anthropic.claude-3-5-sonnet-20241022-v2:0"
    )
    # GEMINI ainda nao tem adaptador real implementado (ver
    # app.integrations.llm.gemini_adapter) - o modelo escolhido aqui fica
    # registrado para quando a integracao existir, mas selecionar
    # llm_provider=GEMINI hoje falha explicitamente ao chamar o LLM.
    llm_gemini_model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="gemini-1.5-flash"
    )

    # --- Multimodalidade aceita em novas analises ---
    # Controla quais modalidades de MIDIA podem ser enviadas em uma nova
    # analise - TEXT nunca e afetado (e um campo direto da analise, nao um
    # upload de midia, ver app.media.validation).
    modality_audio_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    modality_video_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    modality_image_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Visao computacional de video (OpenPose/YOLOv8) ---
    # Toggles independentes por motor (ver app.integrations.vision) -
    # permitem considerar YOLOv8 e OpenPose separadamente sem exigir que
    # os dois estejam instalados/compilados no worker de video.
    vision_detection_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vision_pose_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Amazon Rekognition (imagem/video, enriquecimento OPCIONAL): NUNCA
    # substitui a heuristica de categoria de imagem
    # (app.vision.image_category) nem o worker OpenPose/YOLOv8 de video
    # (Rekognition nao faz estimativa de pose) - apenas adiciona rotulos
    # genericos (ex.: "X-Ray", "Person") como achado MODEL_OBSERVATION
    # complementar. Cada modalidade tem seu proprio interruptor
    # independente (mesmo motivo dos dois motores de video acima: nao ha
    # por que ligar imagem e video juntos). Default `False` segue a mesma
    # convencao "seguro por padrao" - chamar um servico AWS pago e sempre
    # uma decisao explicita do administrador.
    image_recognition_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    vision_rekognition_video_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Qual adaptador real usar quando `image_recognition_enabled` estiver
    # ligado (`AWS_REKOGNITION` ou `AZURE_VISION`, ver
    # `app.integrations.image_recognition`) - so este achado especifico
    # de imagem tem escolha de provedor; o Rekognition Video (video) so
    # tem o adaptador AWS ate hoje, sem equivalente Azure implementado.
    image_recognition_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="AWS_REKOGNITION"
    )

    # --- Amazon Comprehend (analise de sentimento) - resultado sempre
    # contextual, nunca determina risco clinico. Roda sobre o texto
    # adicional da analise (`app.processors.text`) e sobre a transcricao
    # de audio quando disponivel (`app.processors.audio`) - nunca sobre
    # dados clinicos estruturados. Comprehend padrao (nao o Medical, que
    # so suporta ingles dos EUA) tem suporte oficial a portugues (`pt`).
    # Default `False` segue a mesma convencao "seguro por padrao" dos
    # demais servicos AWS pagos deste projeto.
    sentiment_analysis_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Qual adaptador real usar quando `sentiment_analysis_enabled` estiver
    # ligado (`AWS_COMPREHEND` ou `AZURE_LANGUAGE`, ver
    # `app.integrations.sentiment_analysis`).
    sentiment_analysis_provider: Mapped[str] = mapped_column(
        String(20), nullable=False, default="AWS_COMPREHEND"
    )

    # --- Apoio a analise clinica (IA) automatico apos processamento ---
    # Quando ligado, o worker (`app.orchestrator.worker`) chama
    # `app.clinical_support.service.generate_analysis_clinical_support_
    # summary` automaticamente ao final do processamento de cada analise
    # (junto com a consolidacao de risco + geracao do relatorio),
    # eliminando a necessidade do botao manual "Analisar dados clinicos"
    # na tela de revisao. So executa quando ha conteudo CLINICAMENTE
    # RELEVANTE identificado (ver `app.clinical_support.service.
    # should_run_automatic_clinical_support`) - nunca chama o LLM so
    # porque a analise tem midia, se essa midia nao tiver sinal clinico
    # confirmado (ex.: foto de paisagem sem relevancia, video sem pessoa
    # detectada, texto sem termo clinico). Desligado, nenhuma chamada
    # automatica ao LLM ocorre para este proposito - equivalente a nunca
    # clicar o botao manual. Default `False` segue a mesma convencao
    # "seguro por padrao" das demais integracoes de IA deste projeto.
    auto_clinical_support_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
