"""Processador da modalidade AUDIO.

Duracao real e calculada para WAV (`parse_wav_duration_seconds`). Para
MP3/M4A (`audio/mpeg`, `audio/mp4`), o arquivo e convertido para WAV PCM
via `ffmpeg` antes do processamento - assim a analise acustica DSP e a
transcricao funcionam independentemente do formato de entrada original.
Se `ffmpeg` nao estiver disponivel no PATH, o comportamento anterior e
mantido (qualidade MODERATE, duracao indisponivel, sem analise acustica
nem transcricao).

Para WAV PCM tambem roda:

1. **Analise acustica real** (`app.acoustics.voice_analysis`): energia,
   pausas e segmentos de fala extraidos das amostras PCM decodificadas -
   vira achado `MODEL_OBSERVATION`. Quando um limiar heuristico e cruzado,
   gera tambem hipoteses de possivel alteracao vocal (`ASSISTED_HYPOTHESIS`,
   nunca diagnostico).
2. **Transcricao** (`app.integrations.transcription`): adaptador LOCAL
   retorna honestamente "indisponivel" (sem motor de ASR); adaptador
   AZURE_SPEECH (configuravel) produz uma transcricao real. Quando ha
   transcricao, os mesmos termos clinicos candidatos usados pelo
   processador de texto (`app.clinical_nlp.text_analysis`) sao extraidos
   dela, e um rascunho de nota clinica e composto para revisao - nunca
   apresentado como nota finalizada.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.acoustics.voice_analysis import (
    extract_acoustic_features,
    generate_vocal_alteration_hypotheses,
)
from app.core.enums import (
    FindingNature,
    ModalityQualityState,
    ModalityType,
    SentimentAnalysisStatus,
    TranscriptionStatus,
)
from app.integrations.llm import get_llm_adapter
from app.integrations.sentiment_analysis import get_sentiment_analysis_adapter
from app.integrations.sentiment_analysis.base import SentimentAnalysisRequest
from app.integrations.transcription import get_transcription_adapter
from app.integrations.transcription.base import TranscriptionRequest
from app.orchestrator.models import AnalysisModalityState
from app.processors.base import load_approved_media_asset, record_finding
from app.processors.media_analysis import parse_wav_duration_seconds, parse_wav_pcm_samples
from app.processors.quality import (
    MIN_AUDIO_SECONDS_ADEQUATE,
    MIN_AUDIO_SECONDS_MODERATE,
    assess_duration_based_quality,
)
from app.storage import get_storage_adapter

_WAV_MIME_TYPES = ("audio/wav", "audio/x-wav")
_CONVERTIBLE_MIME_TYPES = ("audio/mpeg", "audio/mp3", "audio/mp4")

_logger = logging.getLogger(__name__)

_SENTIMENT_PROVIDER_DISPLAY_NAMES = {
    "azure_language": "Azure AI Language",
    "local": "adaptador local",
}


def _extract_audio_terms_via_llm(db, text: str) -> list[dict]:
    """Extrai termos clínicos da transcrição via LLM. Fallback para NegEx."""
    try:
        adapter = get_llm_adapter(db)
        terms = adapter.extract_clinical_terms(text)
        return terms if terms else []
    except Exception:  # noqa: BLE001
        _logger.warning("LLM extraction failed for audio transcript, fallback to NegEx")
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


def _convert_to_wav(content: bytes, source_mime: str) -> bytes | None:
    """Converte audio MP3/M4A para WAV PCM 16-bit mono 16kHz via ffmpeg.

    Retorna os bytes WAV resultantes, ou None se ffmpeg nao estiver
    disponivel ou a conversao falhar (nenhuma exceção e propagada -
    degradacao graceful para o fluxo anterior sem conversao)."""
    ext_map = {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/mp4": ".m4a"}
    ext = ext_map.get(source_mime, ".mp3")
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as src_file:
            src_file.write(content)
            src_path = Path(src_file.name)
        dst_path = src_path.with_suffix(".wav")
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src_path),
                "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
                str(dst_path),
            ],
            capture_output=True,
            timeout=60,
        )
        src_path.unlink(missing_ok=True)
        if result.returncode != 0:
            _logger.warning(
                "ffmpeg conversion failed (rc=%d): %s", result.returncode, result.stderr[:500]
            )
            dst_path.unlink(missing_ok=True)
            return None
        wav_bytes = dst_path.read_bytes()
        dst_path.unlink(missing_ok=True)
        return wav_bytes
    except FileNotFoundError:
        _logger.warning("ffmpeg not found in PATH - audio conversion unavailable")
        return None
    except Exception as exc:  # noqa: BLE001
        _logger.warning("ffmpeg conversion error: %s", exc)
        return None


def _run_acoustic_analysis(
    db: Session, modality_state: AnalysisModalityState, content: bytes, quality_state
) -> None:
    pcm = parse_wav_pcm_samples(content)
    if pcm is None:
        return

    features = extract_acoustic_features(pcm)
    if features is None:
        return

    observation = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.AUDIO,
        quality_state=quality_state,
        quality_metrics={
            "rms_energy_mean": features.rms_energy_mean,
            "rms_energy_std": features.rms_energy_std,
            "zero_crossing_rate": features.zero_crossing_rate,
            "pause_ratio": features.pause_ratio,
            "voiced_segment_count": features.voiced_segment_count,
            "method": "acoustic_dsp_v1",
        },
        quality_factors=[],
        summary=(
            f"Energia media {features.rms_energy_mean:.4f}, proporcao de pausas "
            f"{features.pause_ratio:.0%}, {features.voiced_segment_count} segmentos de fala."
        ),
        nature=FindingNature.MODEL_OBSERVATION,
    )
    db.add(observation)

    for hypothesis in generate_vocal_alteration_hypotheses(features):
        hypothesis_finding = record_finding(
            modality_state=modality_state,
            modality_type=ModalityType.AUDIO,
            quality_state=quality_state,
            quality_metrics={"label": hypothesis.label, **hypothesis.based_on},
            quality_factors=[],
            summary=hypothesis.detail,
            nature=FindingNature.ASSISTED_HYPOTHESIS,
        )
        db.add(hypothesis_finding)


def _run_sentiment_analysis(
    db: Session, modality_state: AnalysisModalityState, *, text: str
) -> None:
    """Mesmo enriquecimento CONTEXTUAL do processador de TEXT (ver
    `app.processors.text._run_sentiment_analysis`), aqui sobre a
    transcricao do audio em vez do texto adicional - so roda quando ha
    transcricao real (`process_audio_modality` so chama esta funcao
    depois de confirmar `TranscriptionStatus.COMPLETED`)."""
    adapter = get_sentiment_analysis_adapter(db)
    result = adapter.detect_sentiment(SentimentAnalysisRequest(text=text))
    provider_name = _SENTIMENT_PROVIDER_DISPLAY_NAMES.get(result.provider, result.provider)

    if result.status is SentimentAnalysisStatus.UNAVAILABLE:
        summary = f"Analise de sentimento ({provider_name}) indisponivel: {result.error}"
    elif result.status is SentimentAnalysisStatus.FAILED:
        summary = f"Analise de sentimento ({provider_name}) falhou: {result.error}"
    else:
        summary = (
            f"Sentimento identificado na transcricao ({provider_name}, contextual - nao "
            f"determina risco clinico): {result.sentiment}."
        )
        if result.key_phrases:
            summary += f" Termos-chave identificados: {', '.join(result.key_phrases)}."

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.AUDIO,
        quality_state=ModalityQualityState.ADEQUATE,
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
            "source": "audio_transcript",
        },
        quality_factors=[],
        summary=summary,
        nature=FindingNature.MODEL_OBSERVATION,
    )
    db.add(finding)


def _run_transcription(
    db: Session,
    modality_state: AnalysisModalityState,
    media_asset,
    media_format: str,
    content: bytes,
) -> None:
    adapter = get_transcription_adapter()
    request = TranscriptionRequest(
        storage_key=media_asset.storage_key,
        language_code="pt-BR",
        media_format=media_format,
        job_name=f"analysis-{modality_state.analysis_id}-audio-{uuid.uuid4().hex[:8]}",
        # Usado pelo adaptador Azure (Fast Transcription API, upload
        # direto no corpo da requisicao). Bytes ja lidos abaixo para a
        # analise acustica, reaproveitados aqui sem leitura extra do
        # storage.
        audio_bytes=content,
    )
    result = adapter.transcribe(request)

    if result.status is TranscriptionStatus.UNAVAILABLE:
        summary = f"Transcricao indisponivel: {result.error}"
    elif result.status is TranscriptionStatus.FAILED:
        summary = f"Transcricao falhou: {result.error}"
    else:
        summary = f"Transcricao concluida ({result.provider}/{result.engine})."

    transcription_finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.AUDIO,
        quality_state=ModalityQualityState.ADEQUATE,
        quality_metrics={
            "status": result.status.value,
            "provider": result.provider,
            "engine": result.engine,
            "error": result.error,
        },
        quality_factors=[],
        summary=summary,
        nature=FindingNature.MODEL_OBSERVATION,
    )
    db.add(transcription_finding)

    if result.status is not TranscriptionStatus.COMPLETED or not result.transcript_text:
        return

    # Rascunho de nota clinica para revisao - apenas a transcricao
    # formatada como rascunho, nunca uma nota finalizada nem uma
    # conclusao clinica.
    draft_note_finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.AUDIO,
        quality_state=ModalityQualityState.ADEQUATE,
        quality_metrics={"transcript": result.transcript_text, "status": "DRAFT_FOR_REVIEW"},
        quality_factors=[],
        summary=(
            f"Rascunho de nota clinica (transcricao literal, requer revisao): "
            f'"{result.transcript_text}"'
        ),
        nature=FindingNature.MODEL_OBSERVATION,
    )
    db.add(draft_note_finding)

    # Pré-validação de relevância clínica da transcrição: se o conteúdo
    # transcrito não tiver contexto clínico (ex.: conversa casual, música,
    # ruído transcrito), pula sentimento e extração de termos.
    from app.integrations.llm import get_llm_adapter as _get_llm
    from app.integrations.llm.base import LlmTextRelevanceCheckRequest as _RelReq

    transcript_is_relevant = True
    try:
        llm = _get_llm(db)
        rel = llm.check_text_clinical_relevance(_RelReq(text=result.transcript_text))
        transcript_is_relevant = rel.is_clinically_relevant and rel.relevance_percent >= 30
        if not transcript_is_relevant:
            skip_finding = record_finding(
                modality_state=modality_state,
                modality_type=ModalityType.AUDIO,
                quality_state=ModalityQualityState.ADEQUATE,
                quality_metrics={
                    "clinical_relevance": "NOT_RELEVANT",
                    "relevance_percent": rel.relevance_percent,
                    "reason": rel.reason,
                    "source": "audio_transcript",
                },
                quality_factors=["transcricao_sem_relevancia_clinica"],
                summary=(
                    f"Transcrição avaliada com {rel.relevance_percent}% de relevância "
                    f"clínica. {rel.reason} Análise de sentimento e extração de termos "
                    "dispensadas."
                ),
                nature=FindingNature.MODEL_OBSERVATION,
            )
            db.add(skip_finding)
    except Exception:  # noqa: BLE001
        pass  # falha assume relevante, continua normalmente

    if not transcript_is_relevant:
        return

    _run_sentiment_analysis(db, modality_state, text=result.transcript_text)

    for mention in _extract_audio_terms_via_llm(db, result.transcript_text):
        mention_finding = record_finding(
            modality_state=modality_state,
            modality_type=ModalityType.AUDIO,
            quality_state=ModalityQualityState.ADEQUATE,
            quality_metrics={
                "term": mention["term"],
                "negation": mention.get("negation", "AFFIRMED"),
                "certainty": mention.get("certainty", "CONFIRMED"),
                "temporality": mention.get("temporality", "CURRENT"),
                "experiencer": mention.get("experiencer", "PATIENT"),
                "extraction_method": "llm_gpt4o_extraction_v1",
                "source": "audio_transcript",
            },
            quality_factors=[],
            summary=(
                f"Termo clinico candidato (transcricao) '{mention['term']}' "
                f"({mention.get('negation', 'AFFIRMED').lower()}, "
                f"{mention.get('temporality', 'CURRENT').lower()})."
            ),
            nature=FindingNature.MODEL_OBSERVATION,
        )
        db.add(mention_finding)


def process_audio_modality(db: Session, modality_state: AnalysisModalityState) -> None:
    media_asset = load_approved_media_asset(db, modality_state)
    storage = get_storage_adapter()
    content = storage.read_approved_object(media_asset.storage_key)

    is_wav = media_asset.detected_mime_type in _WAV_MIME_TYPES
    wav_content = content  # bytes usados para analise acustica/transcricao

    # Converte MP3/M4A para WAV PCM via ffmpeg, permitindo analise acustica
    # e transcricao independente do formato original de upload.
    if not is_wav and media_asset.detected_mime_type in _CONVERTIBLE_MIME_TYPES:
        converted = _convert_to_wav(content, media_asset.detected_mime_type)
        if converted is not None:
            wav_content = converted
            is_wav = True

    duration_seconds: float | None = None
    if is_wav:
        duration_seconds = parse_wav_duration_seconds(wav_content)

    assessment = assess_duration_based_quality(
        duration_seconds,
        adequate_threshold=MIN_AUDIO_SECONDS_ADEQUATE,
        moderate_threshold=MIN_AUDIO_SECONDS_MODERATE,
    )
    factors = list(assessment.factors)
    if duration_seconds is None and not is_wav:
        factors.append(f"duracao_indisponivel_para_formato_{media_asset.detected_mime_type}")

    summary = (
        f"Audio com duracao de {duration_seconds:.1f}s."
        if duration_seconds is not None
        else "Duracao do audio nao pode ser determinada neste formato."
    )

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.AUDIO,
        quality_state=assessment.state,
        quality_metrics=assessment.metrics,
        quality_factors=factors,
        summary=summary,
    )
    db.add(finding)

    if is_wav and assessment.state not in (
        ModalityQualityState.INSUFFICIENT,
        ModalityQualityState.INVALID,
    ):
        _run_acoustic_analysis(db, modality_state, wav_content, assessment.state)
        _run_transcription(
            db, modality_state, media_asset, media_format="wav", content=wav_content
        )
