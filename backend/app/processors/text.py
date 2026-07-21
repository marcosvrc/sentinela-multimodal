"""Processador da modalidade TEXT.

O texto adicional (`Analysis.additional_text`) e o proprio dado - a
avaliacao de qualidade e deterministica, baseada em tamanho (legibilidade
como fator de qualidade para texto). Nao ha modalidade sem texto: se a
analise foi submetida com um `AnalysisModalityState` para TEXT,
`additional_text` deve existir (invariante garantida por
`app.orchestrator.service.submit_analysis`).

Alem da qualidade, o processador roda a analise clinica textual real
(`app.clinical_nlp.text_analysis.analyze_clinical_text`): negacao,
temporalidade, certeza e experienciador por termo clinico candidato. Cada
mencao vira um `ModalityFinding` proprio com `nature=MODEL_OBSERVATION` -
e uma observacao derivada de um metodo determinístico sobre o texto,
nunca uma classificacao de risco (o motor de regras, `app.rules_engine`,
continua sendo a unica fonte de risco).

Quando a feature flag `sentiment_analysis_enabled` esta ligada (tela
`/admin/feature-flags`), roda tambem Amazon Comprehend `DetectSentiment`
(`app.integrations.sentiment_analysis`) sobre o mesmo texto - sempre
CONTEXTUAL (nunca determina risco clinico por si so), gravado como achado
`MODEL_OBSERVATION` proprio. Como `app.risk_consolidation.service.
consolidate_analysis_risk` so envia ao LLM achados `nature=ORIGINAL_DATA`,
o sentimento nunca alcanca o prompt de consolidacao de risco - fica
disponivel apenas no laudo, como as demais observacoes derivadas de
modelo.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clinical_nlp.text_analysis import analyze_clinical_text
from app.core.enums import (
    FindingNature,
    ModalityQualityState,
    ModalityType,
    SentimentAnalysisStatus,
)
from app.integrations.sentiment_analysis import get_sentiment_analysis_adapter
from app.integrations.sentiment_analysis.base import SentimentAnalysisRequest
from app.media.models import Analysis
from app.orchestrator.models import AnalysisModalityState
from app.processors.base import record_finding
from app.processors.quality import assess_text_quality


class TextContentMissingError(Exception):
    """`additional_text` ausente para um estado de modalidade TEXT - invariante violada."""


_SENTIMENT_PROVIDER_DISPLAY_NAMES = {
    "aws_comprehend": "Amazon Comprehend",
    "azure_language": "Azure AI Language",
    "local": "adaptador local",
}


def _run_sentiment_analysis(
    db: Session,
    modality_state: AnalysisModalityState,
    *,
    text: str,
    quality_state: ModalityQualityState,
) -> None:
    adapter = get_sentiment_analysis_adapter(db)
    result = adapter.detect_sentiment(SentimentAnalysisRequest(text=text))
    provider_name = _SENTIMENT_PROVIDER_DISPLAY_NAMES.get(result.provider, result.provider)

    if result.status is SentimentAnalysisStatus.UNAVAILABLE:
        summary = f"Analise de sentimento ({provider_name}) indisponivel: {result.error}"
    elif result.status is SentimentAnalysisStatus.FAILED:
        summary = f"Analise de sentimento ({provider_name}) falhou: {result.error}"
    else:
        summary = (
            f"Sentimento identificado ({provider_name}, contextual - nao determina risco "
            f"clinico): {result.sentiment}."
        )
        if result.key_phrases:
            summary += f" Termos-chave identificados: {', '.join(result.key_phrases)}."

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.TEXT,
        quality_state=quality_state,
        quality_metrics={
            "status": result.status.value,
            "provider": result.provider,
            "sentiment": result.sentiment,
            "key_phrases": list(result.key_phrases) if result.key_phrases else None,
            "scores": (
                {
                    "positive": result.scores.positive,
                    "negative": result.scores.negative,
                    "neutral": result.scores.neutral,
                    "mixed": result.scores.mixed,
                }
                if result.scores is not None
                else None
            ),
            "error": result.error,
        },
        quality_factors=[],
        summary=summary,
        nature=FindingNature.MODEL_OBSERVATION,
    )
    db.add(finding)


def process_text_modality(db: Session, modality_state: AnalysisModalityState) -> None:
    analysis = db.scalar(select(Analysis).where(Analysis.id == modality_state.analysis_id))
    if analysis is None or not analysis.additional_text:
        raise TextContentMissingError(
            "Analise sem texto adicional para um estado de modalidade TEXT."
        )

    assessment = assess_text_quality(analysis.additional_text)
    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.TEXT,
        quality_state=assessment.state,
        quality_metrics=assessment.metrics,
        quality_factors=assessment.factors,
        summary=(
            f"Texto com {assessment.metrics['length']} caracteres "
            f"({assessment.metrics['word_count']} palavras)."
        ),
    )
    db.add(finding)

    if assessment.state not in (ModalityQualityState.INSUFFICIENT, ModalityQualityState.INVALID):
        _run_sentiment_analysis(
            db,
            modality_state,
            text=analysis.additional_text,
            quality_state=assessment.state,
        )

    for mention in analyze_clinical_text(analysis.additional_text):
        observation = record_finding(
            modality_state=modality_state,
            modality_type=ModalityType.TEXT,
            quality_state=ModalityQualityState.ADEQUATE,
            quality_metrics={
                "term": mention.term,
                "negation": mention.negation.value,
                "certainty": mention.certainty.value,
                "temporality": mention.temporality.value,
                "experiencer": mention.experiencer.value,
                "span": {"start": mention.start, "end": mention.end},
                "extraction_method": "rule_based_negex_context_v1",
            },
            quality_factors=[],
            summary=(
                f"Termo clinico candidato '{mention.term}' "
                f"({mention.negation.value.lower()}, {mention.temporality.value.lower()}, "
                f"{mention.certainty.value.lower()}, "
                f"experienciador={mention.experiencer.value.lower()}) "
                f'na frase: "{mention.sentence}".'
            ),
            nature=FindingNature.MODEL_OBSERVATION,
        )
        db.add(observation)
