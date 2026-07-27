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

Antes de rodar a analise de sentimento (Azure AI Language), o processador
valida a relevancia clinica do texto via LLM. Se o texto nao tiver
relacao com contexto clinico (ex.: receita culinaria, texto generico),
a analise de sentimento e PULADA - evitando custos desnecessarios com
servicos de nuvem e achados sem significado clinico.

Quando a feature flag `sentiment_analysis_enabled` esta ligada (tela
`/admin/feature-flags`), roda Azure AI Language `SentimentAnalysis`
(`app.integrations.sentiment_analysis`) sobre o texto - sempre
CONTEXTUAL (nunca determina risco clinico por si so), gravado como achado
`MODEL_OBSERVATION` proprio.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import (
    FindingNature,
    ModalityQualityState,
    ModalityType,
    SentimentAnalysisStatus,
)
from app.integrations.llm import get_llm_adapter
from app.integrations.llm.base import LlmTextRelevanceCheckRequest
from app.integrations.sentiment_analysis import get_sentiment_analysis_adapter
from app.integrations.sentiment_analysis.base import SentimentAnalysisRequest
from app.media.models import Analysis
from app.orchestrator.models import AnalysisModalityState
from app.processors.base import record_finding
from app.processors.quality import assess_text_quality

_logger = logging.getLogger(__name__)

# Limiar minimo de relevancia clinica (0-100) para rodar a analise de
# sentimento. Abaixo disso, o texto e considerado irrelevante para o
# contexto clinico e a analise de sentimento e pulada.
_MIN_CLINICAL_RELEVANCE_PERCENT = 30


def _extract_terms_via_llm(db: Session, text: str) -> list[dict]:
    """Extrai termos clínicos via LLM (dinâmico, sem lista fixa).
    Fallback para NegEx local se o LLM falhar."""
    try:
        adapter = get_llm_adapter(db)
        terms = adapter.extract_clinical_terms(text)
        return terms if terms else []
    except Exception:  # noqa: BLE001
        _logger.warning("LLM extraction failed, falling back to NegEx/ConText")
        from app.clinical_nlp.text_analysis import analyze_clinical_text
        return [
            {
                "term": m.term,
                "negation": m.negation.value,
                "temporality": m.temporality.value,
                "certainty": m.certainty.value,
                "experiencer": m.experiencer.value,
            }
            for m in analyze_clinical_text(text)
        ]


class TextContentMissingError(Exception):
    """`additional_text` ausente para um estado de modalidade TEXT - invariante violada."""


_SENTIMENT_PROVIDER_DISPLAY_NAMES = {
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

    # Pré-validação de relevância clínica via LLM: antes de rodar análise
    # de sentimento (Azure, custo por chamada) e extração de termos,
    # verifica se o texto tem contexto clínico mínimo. Se não tiver (ex.:
    # receita culinária, texto aleatório), pula o processamento pesado e
    # registra o motivo explicitamente.
    text_is_clinically_relevant = True
    relevance_percent = 100
    relevance_reason = ""
    try:
        adapter = get_llm_adapter(db)
        relevance_result = adapter.check_text_clinical_relevance(
            LlmTextRelevanceCheckRequest(text=analysis.additional_text)
        )
        text_is_clinically_relevant = relevance_result.is_clinically_relevant
        relevance_percent = relevance_result.relevance_percent
        relevance_reason = relevance_result.reason
    except Exception:  # noqa: BLE001
        # Se a validação falhar, assume relevante (não bloqueia o fluxo)
        _logger.warning("Falha na validacao de relevancia clinica do texto - assumindo relevante")

    if not text_is_clinically_relevant or relevance_percent < _MIN_CLINICAL_RELEVANCE_PERCENT:
        # Texto sem relevância clínica — registra o achado e pula
        # sentimento/extração de termos
        irrelevant_finding = record_finding(
            modality_state=modality_state,
            modality_type=ModalityType.TEXT,
            quality_state=ModalityQualityState.ADEQUATE,
            quality_metrics={
                "clinical_relevance": "NOT_RELEVANT",
                "relevance_percent": relevance_percent,
                "reason": relevance_reason,
            },
            quality_factors=["conteudo_sem_relevancia_clinica"],
            summary=(
                f"Texto avaliado com {relevance_percent}% de relevância clínica. "
                f"{relevance_reason} A análise de sentimento e a extração de termos "
                "foram dispensadas por falta de contexto clínico."
            ),
            nature=FindingNature.MODEL_OBSERVATION,
        )
        db.add(irrelevant_finding)
        return

    if assessment.state not in (ModalityQualityState.INSUFFICIENT, ModalityQualityState.INVALID):
        _run_sentiment_analysis(
            db,
            modality_state,
            text=analysis.additional_text,
            quality_state=assessment.state,
        )

    for mention in _extract_terms_via_llm(db, analysis.additional_text):
        observation = record_finding(
            modality_state=modality_state,
            modality_type=ModalityType.TEXT,
            quality_state=ModalityQualityState.ADEQUATE,
            quality_metrics={
                "term": mention["term"],
                "negation": mention.get("negation", "AFFIRMED"),
                "certainty": mention.get("certainty", "CONFIRMED"),
                "temporality": mention.get("temporality", "CURRENT"),
                "experiencer": mention.get("experiencer", "PATIENT"),
                "extraction_method": "llm_gpt4o_extraction_v1",
            },
            quality_factors=[],
            summary=(
                f"Termo clinico candidato '{mention['term']}' "
                f"({mention.get('negation', 'AFFIRMED').lower()}, "
                f"{mention.get('temporality', 'CURRENT').lower()}, "
                f"{mention.get('certainty', 'CONFIRMED').lower()}, "
                f"experienciador={mention.get('experiencer', 'PATIENT').lower()})."
            ),
            nature=FindingNature.MODEL_OBSERVATION,
        )
        db.add(observation)
