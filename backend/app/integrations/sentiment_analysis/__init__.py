"""Selecao do adaptador de analise de sentimento por feature flag (mesmo
padrao de `app.integrations.image_recognition` - a decisao de ligar/
desligar vem da linha singleton `app.feature_flags`, banco, mutavel em
runtime via tela `/admin/feature-flags`, nunca de `Settings`/`.env`). Por
isso esta fabrica exige `db: Session` e nunca usa `@lru_cache`.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.feature_flags.service import get_feature_flags
from app.integrations.sentiment_analysis.base import SentimentAnalysisAdapter
from app.integrations.sentiment_analysis.local import LocalUnavailableSentimentAnalysisAdapter


def get_sentiment_analysis_adapter(db: Session) -> SentimentAnalysisAdapter:
    flags = get_feature_flags(db)

    if not flags.sentiment_analysis_enabled:
        return LocalUnavailableSentimentAnalysisAdapter()

    settings = get_settings()
    if not settings.azure_language_key or not settings.azure_language_endpoint:
        raise RuntimeError(
            "Feature flag sentiment_analysis_enabled exige AZURE_LANGUAGE_KEY e "
            "AZURE_LANGUAGE_ENDPOINT configurados."
        )

    import httpx

    from app.integrations.sentiment_analysis.azure_language import (
        AzureLanguageSentimentAdapter,
    )

    return AzureLanguageSentimentAdapter(
        http_client=httpx.Client(timeout=30.0),  # type: ignore[arg-type]
        subscription_key=settings.azure_language_key,
        endpoint=settings.azure_language_endpoint,
    )
