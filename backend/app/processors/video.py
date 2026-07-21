"""Processador da modalidade VIDEO.

Duracao real e calculada para MP4/MOV (`parse_isobmff_duration_seconds`,
ISO BMFF - `video/mp4` e `video/quicktime` sao os dois tipos aceitos por
`app.media.validation.ALLOWED_MIME_TYPES[VIDEO]`, ambos ISO BMFF).

Tambem roda a **analise de visao computacional** (`app.integrations.
vision`): adaptador LOCAL retorna honestamente "indisponivel" (sem motor
de pose/deteccao); adaptador OPENPOSE_YOLOV8 (configuravel, worker
self-hosted escolhido para nao depender de um servico de visao gerenciado
de terceiros nesse caminho) amostra quadros do video e roda estimativa de
pose (OpenPose) + deteccao de objetos (YOLOv8) sobre cada um, virando
achados `MODEL_OBSERVATION`. Quando nenhum quadro amostrado tem uma pessoa
detectada, gera tambem uma hipotese de possivel ausencia de paciente no
campo de captura (`ASSISTED_HYPOTHESIS`, nunca diagnostico - inferencias
como dor, confusao, sangramento ou erro procedimental nao podem ser
tratadas como diagnostico apenas com base no video).

Quando a feature flag `vision_rekognition_video_enabled` esta ligada
(tela `/admin/feature-flags`), roda tambem Amazon Rekognition Video
(`app.integrations.video_recognition`) como fonte COMPLEMENTAR ao worker
self-hosted acima: rotulos genericos com timestamp (ex.: "Person", "Bed"),
gravados como achado `MODEL_OBSERVATION` SEPARADO do achado de
pose/deteccao - o Rekognition nao faz estimativa de pose (a analise de
pose e o requisito central desta modalidade), entao nunca substitui nem
se mistura ao resumo do OpenPose/YOLOv8.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.enums import FindingNature, ModalityQualityState, ModalityType, VisionAnalysisStatus
from app.integrations.video_recognition import get_video_recognition_adapter
from app.integrations.video_recognition.base import VideoRecognitionRequest
from app.integrations.vision import get_vision_adapter
from app.integrations.vision.base import VideoAnalysisRequest, VideoAnalysisResult
from app.orchestrator.models import AnalysisModalityState
from app.processors.base import load_approved_media_asset, record_finding
from app.processors.media_analysis import parse_isobmff_duration_seconds
from app.processors.quality import (
    MIN_VIDEO_SECONDS_ADEQUATE,
    MIN_VIDEO_SECONDS_MODERATE,
    assess_duration_based_quality,
)
from app.storage import get_storage_adapter
from app.vision.clinical_relevance import assess_label_clinical_relevance

_ISOBMFF_MIME_TYPES = ("video/mp4", "video/quicktime")
_MEDIA_FORMAT_BY_MIME = {"video/mp4": "mp4", "video/quicktime": "mov"}


def _run_vision_analysis(
    db: Session,
    modality_state: AnalysisModalityState,
    *,
    content: bytes,
    storage_key: str,
    media_format: str,
    quality_state: ModalityQualityState,
) -> None:
    from app.core.config import get_settings

    adapter = get_vision_adapter(db)
    request = VideoAnalysisRequest(
        storage_key=storage_key,
        media_format=media_format,
        max_sample_frames=get_settings().vision_max_sample_frames,
        video_bytes=content,
    )
    result = adapter.analyze(request)

    _record_vision_summary_finding(db, modality_state, result, quality_state)

    if result.status is not VisionAnalysisStatus.COMPLETED:
        return

    _record_vision_absence_hypothesis(db, modality_state, result, quality_state)


def _record_vision_summary_finding(
    db: Session,
    modality_state: AnalysisModalityState,
    result: VideoAnalysisResult,
    quality_state: ModalityQualityState,
) -> None:
    if result.status is VisionAnalysisStatus.UNAVAILABLE:
        summary = f"Analise de visao computacional indisponivel: {result.error}"
    elif result.status is VisionAnalysisStatus.FAILED:
        summary = f"Analise de visao computacional falhou: {result.error}"
    else:
        # Cada motor (pose/deteccao) pode estar desligado independentemente
        # (feature flags vision_pose_enabled/vision_detection_enabled) - o
        # resumo so menciona o resultado de um motor quando ele de fato
        # rodou, nunca "0 deteccoes" para um motor desligado (isso
        # pareceria um achado negativo real, quando na verdade a analise
        # nem foi tentada).
        summary_parts = [f"{result.frames_analyzed} quadro(s) amostrado(s)"]
        if result.pose_enabled:
            total_persons = sum(p.person_count for p in result.pose_findings)
            summary_parts.append(f"{total_persons} deteccao(oes) de pessoa (pose)")
        if result.detection_enabled:
            distinct_labels = sorted({d.label for d in result.detection_findings})
            summary_parts.append(f"objetos identificados: {', '.join(distinct_labels) or 'nenhum'}")
        summary = ", ".join(summary_parts) + "."

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.VIDEO,
        quality_state=quality_state,
        quality_metrics={
            "status": result.status.value,
            "provider": result.provider,
            "frames_analyzed": result.frames_analyzed,
            "pose_enabled": result.pose_enabled,
            "detection_enabled": result.detection_enabled,
            "pose_findings": [
                {
                    "frame_index": p.frame_index,
                    "person_count": p.person_count,
                    "mean_keypoint_confidence": p.mean_keypoint_confidence,
                    "model_version": p.model_version,
                }
                for p in result.pose_findings
            ],
            "detection_findings": [
                {
                    "frame_index": d.frame_index,
                    "label": d.label,
                    "confidence": d.confidence,
                    "model_version": d.model_version,
                }
                for d in result.detection_findings
            ],
            "error": result.error,
        },
        quality_factors=[],
        summary=summary,
        nature=FindingNature.MODEL_OBSERVATION,
    )
    db.add(finding)


def _record_vision_absence_hypothesis(
    db: Session,
    modality_state: AnalysisModalityState,
    result: VideoAnalysisResult,
    quality_state: ModalityQualityState,
) -> None:
    # So gera hipotese quando o motor de pose estava LIGADO e rodou sobre
    # quadros, e NENHUM tem pessoa detectada - achado real (agregado dos
    # quadros amostrados), nunca uma conclusao clinica. Pode indicar
    # enquadramento de camera fora do paciente tanto quanto qualquer outra
    # causa; cabe ao profissional interpretar. Com vision_pose_enabled=
    # false nao ha achado de pose nenhum - a ausencia de `pose_findings`
    # aqui significaria "motor desligado", nunca "ninguem detectado".
    if not result.pose_enabled or not result.pose_findings:
        return
    if any(p.person_count > 0 for p in result.pose_findings):
        return

    hypothesis = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.VIDEO,
        quality_state=quality_state,
        quality_metrics={
            "label": "possivel_ausencia_de_pessoa_no_campo_de_captura",
            "frames_analyzed": result.frames_analyzed,
        },
        quality_factors=[],
        summary=(
            f"Nenhuma pessoa detectada nos {result.frames_analyzed} quadro(s) amostrado(s) - "
            "pode indicar ausencia do paciente no campo de captura ou limitacao do "
            "enquadramento; nao e um diagnostico."
        ),
        nature=FindingNature.ASSISTED_HYPOTHESIS,
    )
    db.add(hypothesis)


def _run_video_recognition(
    db: Session,
    modality_state: AnalysisModalityState,
    *,
    storage_key: str,
    quality_state: ModalityQualityState,
) -> None:
    adapter = get_video_recognition_adapter(db)
    request = VideoRecognitionRequest(
        storage_key=storage_key,
        job_name=f"analysis-{modality_state.analysis_id}-video-rekognition-{uuid.uuid4().hex[:8]}",
    )
    result = adapter.detect_labels(request)

    clinical_relevance = None
    if result.status is VisionAnalysisStatus.UNAVAILABLE:
        summary = f"Reconhecimento de video (Amazon Rekognition) indisponivel: {result.error}"
    elif result.status is VisionAnalysisStatus.FAILED:
        summary = f"Reconhecimento de video (Amazon Rekognition) falhou: {result.error}"
    else:
        distinct_labels = sorted({label.label for label in result.labels})
        # Mesmo guardrail de relevancia clinica do processador IMAGE (ver
        # `app.vision.clinical_relevance`) - rotulos genericos de video
        # tem a mesma limitacao (nao distinguem gravacao clinica de video
        # qualquer). Achados nao relevantes/nao avaliaveis sao informados
        # ao usuario e excluidos das consideracoes finais.
        clinical_relevance = assess_label_clinical_relevance(
            tuple(label.label for label in result.labels)
        )
        labels_text = ", ".join(distinct_labels) or "nenhum rotulo"
        base_summary = (
            f"Rotulos identificados (Amazon Rekognition, complementar ao worker de pose/"
            f"deteccao): {labels_text}."
        )
        if clinical_relevance.relevant in (False, None):
            summary = f"{base_summary} AVISO: {clinical_relevance.reason}"
        else:
            summary = base_summary

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.VIDEO,
        quality_state=quality_state,
        quality_metrics={
            "status": result.status.value,
            "provider": result.provider,
            "labels": [
                {
                    "label": label.label,
                    "confidence": label.confidence,
                    "timestamp_millis": label.timestamp_millis,
                }
                for label in result.labels
            ],
            "error": result.error,
            "clinical_relevance": (
                {
                    True: "RELEVANT",
                    False: "NOT_RELEVANT",
                    None: "UNDETERMINED",
                }[clinical_relevance.relevant]
                if clinical_relevance is not None
                else None
            ),
            "clinical_relevance_reason": (
                clinical_relevance.reason if clinical_relevance is not None else None
            ),
        },
        quality_factors=[],
        summary=summary,
        nature=FindingNature.MODEL_OBSERVATION,
    )
    db.add(finding)


def process_video_modality(db: Session, modality_state: AnalysisModalityState) -> None:
    media_asset = load_approved_media_asset(db, modality_state)
    storage = get_storage_adapter()
    content = storage.read_approved_object(media_asset.storage_key)

    duration_seconds = parse_isobmff_duration_seconds(content)

    assessment = assess_duration_based_quality(
        duration_seconds,
        adequate_threshold=MIN_VIDEO_SECONDS_ADEQUATE,
        moderate_threshold=MIN_VIDEO_SECONDS_MODERATE,
    )
    summary = (
        f"Video com duracao de {duration_seconds:.1f}s."
        if duration_seconds is not None
        else "Duracao do video nao pode ser determinada a partir do arquivo."
    )

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.VIDEO,
        quality_state=assessment.state,
        quality_metrics=assessment.metrics,
        quality_factors=assessment.factors,
        summary=summary,
    )
    db.add(finding)

    # `detected_mime_type` guarda o resultado literal da assinatura de
    # arquivo (`container/isobmff` para MP4/MOV - ambos usam o mesmo
    # container ISO BMFF e a assinatura por si so nao distingue um do
    # outro, ver app.media.validation.detect_mime_type_from_signature).
    # O MIME especifico ja foi validado contra essa assinatura em
    # `signature_matches_declared_mime` na confirmacao do upload; usar
    # `declared_mime_type` aqui e seguro e e o unico campo que de fato
    # diferencia MP4 de MOV.
    media_format = _MEDIA_FORMAT_BY_MIME.get(media_asset.declared_mime_type)
    if media_format is not None and assessment.state not in (
        ModalityQualityState.INSUFFICIENT,
        ModalityQualityState.INVALID,
    ):
        _run_vision_analysis(
            db,
            modality_state,
            content=content,
            storage_key=media_asset.storage_key,
            media_format=media_format,
            quality_state=assessment.state,
        )
        _run_video_recognition(
            db,
            modality_state,
            storage_key=media_asset.storage_key,
            quality_state=assessment.state,
        )
