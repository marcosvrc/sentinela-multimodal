"""Classificacao de qualidade por modalidade.

Cada modalidade produz uma avaliacao de qualidade independente do achado
clinico. Essa avaliacao informa estado (adequada, moderada, insuficiente
ou invalida), metricas disponiveis e fatores como ruido, resolucao,
iluminacao, oclusao, duracao, perda de frames, idioma ou legibilidade.

Os limiares aqui sao heuristicas deliberadamente simples e documentadas
(nao sao um modelo de ML): servem para nao aceitar silenciosamente um
arquivo estruturalmente pobre demais para qualquer analise (ex: 2 segundos
de audio, imagem 40x40) enquanto os processadores reais de reconhecimento
de conteudo (transcricao, visao computacional) nao existem.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.enums import ModalityQualityState

# Resolucao minima abaixo da qual uma imagem clinica e considerada
# insuficiente para qualquer avaliacao (arbitrario, mas alinhado ao "muito
# pequena para qualquer uso" - refinavel por protocolo clinico depois).
MIN_IMAGE_WIDTH_ADEQUATE = 480
MIN_IMAGE_WIDTH_MODERATE = 200

MIN_AUDIO_SECONDS_ADEQUATE = 3.0
MIN_AUDIO_SECONDS_MODERATE = 1.0

MIN_VIDEO_SECONDS_ADEQUATE = 3.0
MIN_VIDEO_SECONDS_MODERATE = 1.0

MIN_TEXT_LENGTH_ADEQUATE = 60
MIN_TEXT_LENGTH_MODERATE = 20


@dataclass(frozen=True)
class QualityAssessment:
    state: ModalityQualityState
    metrics: dict[str, float | int | str | None]
    factors: list[str]


def assess_image_quality(width: int | None, height: int | None) -> QualityAssessment:
    if width is None or height is None:
        return QualityAssessment(
            state=ModalityQualityState.MODERATE,
            metrics={"width": width, "height": height},
            factors=["resolucao_nao_determinada"],
        )

    smaller_dimension = min(width, height)
    if smaller_dimension < MIN_IMAGE_WIDTH_MODERATE:
        state = ModalityQualityState.INSUFFICIENT
        factors = ["resolucao_baixa"]
    elif smaller_dimension < MIN_IMAGE_WIDTH_ADEQUATE:
        state = ModalityQualityState.MODERATE
        factors = ["resolucao_limitada"]
    else:
        state = ModalityQualityState.ADEQUATE
        factors = []

    return QualityAssessment(
        state=state, metrics={"width": width, "height": height}, factors=factors
    )


def assess_duration_based_quality(
    duration_seconds: float | None,
    *,
    adequate_threshold: float,
    moderate_threshold: float,
) -> QualityAssessment:
    if duration_seconds is None:
        return QualityAssessment(
            state=ModalityQualityState.MODERATE,
            metrics={"duration_seconds": None},
            factors=["duracao_nao_determinada_neste_ambiente"],
        )

    if duration_seconds < moderate_threshold:
        state = ModalityQualityState.INSUFFICIENT
        factors = ["duracao_muito_curta"]
    elif duration_seconds < adequate_threshold:
        state = ModalityQualityState.MODERATE
        factors = ["duracao_limitada"]
    else:
        state = ModalityQualityState.ADEQUATE
        factors = []

    return QualityAssessment(
        state=state, metrics={"duration_seconds": duration_seconds}, factors=factors
    )


def assess_text_quality(text: str) -> QualityAssessment:
    stripped = text.strip()
    length = len(stripped)
    word_count = len(stripped.split())

    if length == 0:
        state = ModalityQualityState.INVALID
        factors = ["texto_vazio"]
    elif length < MIN_TEXT_LENGTH_MODERATE:
        state = ModalityQualityState.INSUFFICIENT
        factors = ["texto_muito_curto"]
    elif length < MIN_TEXT_LENGTH_ADEQUATE:
        state = ModalityQualityState.MODERATE
        factors = ["texto_conciso"]
    else:
        state = ModalityQualityState.ADEQUATE
        factors = []

    return QualityAssessment(
        state=state,
        metrics={"length": length, "word_count": word_count},
        factors=factors,
    )
