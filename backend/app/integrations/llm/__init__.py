"""Selecao do adaptador de LLM por configuracao (mesmo padrao de app.storage/app.queue).

Diferente dos demais adaptadores (storage/queue/transcricao/visao), aqui a
fonte de verdade da selecao e a linha singleton de `app.feature_flags`
(banco, mutavel em runtime via tela `/admin/feature-flags`), NAO
`Settings`/`.env` - por isso esta fabrica exige `db: Session` e nunca usa
`@lru_cache` (o resultado precisa refletir a flag mais recente a cada
chamada, sem exigir reiniciar o processo). `Settings.llm_provider`/
`openai_api_key` continuam sendo a fonte da CREDENCIAL (nunca gravada no
banco) - a flag decide apenas SE/QUAL provider usar.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import LlmProvider
from app.feature_flags.service import get_feature_flags
from app.integrations.llm.base import LlmAdapter
from app.integrations.llm.local import LocalTemplateLlmAdapter


def get_llm_adapter(db: Session) -> LlmAdapter:
    flags = get_feature_flags(db)
    settings = get_settings()

    if not flags.llm_provider_enabled:
        return LocalTemplateLlmAdapter()

    provider = LlmProvider(flags.llm_provider)

    if provider is LlmProvider.LOCAL:
        return LocalTemplateLlmAdapter()

    if provider is LlmProvider.OPENAI:
        if not settings.openai_api_key:
            raise RuntimeError(
                "Feature flag llm_provider=OPENAI exige OPENAI_API_KEY configurado no ambiente."
            )
        from app.integrations.llm.openai_adapter import OpenAiLlmAdapter

        return OpenAiLlmAdapter(api_key=settings.openai_api_key, model=flags.llm_openai_model)

    if provider is LlmProvider.BEDROCK:
        # Sem credencial de API externa - usa as mesmas credenciais IAM do
        # processo ja usadas por S3/SQS/Transcribe/Rekognition (boto3),
        # apenas a permissao bedrock:InvokeModel precisa estar concedida e
        # o acesso ao modelo liberado no console Bedrock da conta/regiao.
        from app.integrations.llm.bedrock_adapter import BedrockLlmAdapter

        return BedrockLlmAdapter(region=settings.aws_region, model_id=flags.llm_bedrock_model)

    if provider is LlmProvider.GEMINI:
        # Registrado na tela de feature flags para planejamento, mas SEM
        # adaptador real implementado ainda - falha explicitamente em vez
        # de silenciosamente cair para outro provider (nunca fingir que
        # uma integracao existe).
        raise RuntimeError(
            "Integracao com Gemini ainda nao foi implementada neste projeto. "
            "Desligue 'Usar Gemini' ou selecione outro provedor na tela de feature flags."
        )

    raise RuntimeError(f"Provedor de LLM desconhecido: {flags.llm_provider}")
