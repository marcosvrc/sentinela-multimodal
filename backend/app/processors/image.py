"""Processador da modalidade IMAGE.

Le os bytes aprovados (`storage.read_approved_object`) e extrai dimensoes
reais via `app.processors.media_analysis` (PNG/JPEG, os dois tipos aceitos
por `app.media.validation.ALLOWED_MIME_TYPES[IMAGE]`). Qualidade e avaliada
por resolucao.

Roda tambem o roteamento por categoria (`app.vision.image_category`):
classifica a imagem como fotografia clinica, documento digitalizado ou
radiologica (heuristica real de cor/textura sobre os pixels, nao um
classificador clinico treinado - ver limitacoes no docstring daquele
modulo) e localiza a regiao de maior densidade de borda como aproximacao
de "area de interesse". Cada classificacao vira um achado
`MODEL_OBSERVATION` proprio - nunca altera a qualidade estrutural ja
calculada nem produz diagnostico.

Quando a feature flag `image_recognition_enabled` esta ligada (tela
`/admin/feature-flags`), roda tambem Azure AI Vision Image Analysis
(`app.integrations.image_recognition`) como ENRIQUECIMENTO opcional:
rotulos genericos (ex.: "X-Ray", "Person") somados a heuristica de
categoria acima, nunca a substituindo. Com a flag desligada (padrao) ou o
adaptador retornando `UNAVAILABLE`/`FAILED`, o achado ainda e gravado
(honesto sobre a indisponibilidade), mesmo principio dos demais
adaptadores reais do projeto.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.enums import FindingNature, ModalityQualityState, ModalityType, VisionAnalysisStatus
from app.integrations.image_recognition import get_image_recognition_adapter
from app.integrations.image_recognition.base import ImageRecognitionRequest
from app.orchestrator.models import AnalysisModalityState
from app.processors.base import load_approved_media_asset, record_finding
from app.processors.media_analysis import (
    ImageDimensions,
    parse_jpeg_dimensions,
    parse_png_dimensions,
)
from app.processors.quality import assess_image_quality
from app.storage import get_storage_adapter
from app.vision.clinical_relevance import assess_label_clinical_relevance
from app.vision.image_category import classify_image_category, locate_region_of_interest


def _parse_dimensions(detected_mime_type: str | None, content: bytes) -> ImageDimensions | None:
    if detected_mime_type == "image/png":
        return parse_png_dimensions(content)
    if detected_mime_type == "image/jpeg":
        return parse_jpeg_dimensions(content)
    # Fallback: tenta ambos, pois deteccao por assinatura ja e conservadora.
    return parse_png_dimensions(content) or parse_jpeg_dimensions(content)


_PROVIDER_DISPLAY_NAMES = {
    "azure_vision": "Azure AI Vision",
    "local": "adaptador local",
}


def _run_image_recognition(
    db: Session,
    modality_state: AnalysisModalityState,
    *,
    storage_key: str,
    content: bytes,
    quality_state: ModalityQualityState,
) -> None:
    adapter = get_image_recognition_adapter(db)
    result = adapter.detect_labels(
        ImageRecognitionRequest(storage_key=storage_key, image_bytes=content)
    )
    provider_name = _PROVIDER_DISPLAY_NAMES.get(result.provider, result.provider)

    clinical_relevance = None
    if result.status is VisionAnalysisStatus.UNAVAILABLE:
        summary = f"Reconhecimento de imagem ({provider_name}) indisponivel: {result.error}"
    elif result.status is VisionAnalysisStatus.FAILED:
        summary = f"Reconhecimento de imagem ({provider_name}) falhou: {result.error}"
    else:
        distinct_labels = ", ".join(label.label for label in result.labels) or "nenhum rotulo"
        # Guardrail de relevancia clinica (app.vision.clinical_relevance):
        # o adaptador (Azure AI Vision) devolve rotulos GENERICOS de
        # objeto, sem nocao de contexto clinico - uma foto de
        # paisagem seria classificada com a mesma naturalidade que uma
        # fotografia clinica se este guardrail nao existisse. Quando o
        # conteudo nao parece clinico (ou nao ha como confirmar), o
        # usuario e informado explicitamente aqui, e o achado e EXCLUIDO
        # das consideracoes finais (ver `app.clinical_support.service` -
        # filtra por `clinical_relevance != "NOT_RELEVANT"/"UNDETERMINED"`).
        clinical_relevance = assess_label_clinical_relevance(
            tuple(label.label for label in result.labels)
        )
        if clinical_relevance.relevant is False:
            summary = (
                f"Rotulos identificados ({provider_name}): {distinct_labels}. "
                f"AVISO: {clinical_relevance.reason}"
            )
        elif clinical_relevance.relevant is None:
            summary = (
                f"Rotulos identificados ({provider_name}): {distinct_labels}. "
                f"AVISO: {clinical_relevance.reason}"
            )
        else:
            summary = f"Rotulos identificados ({provider_name}): {distinct_labels}."

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.IMAGE,
        quality_state=quality_state,
        quality_metrics={
            "status": result.status.value,
            "provider": result.provider,
            "labels": [
                {"label": label.label, "confidence": label.confidence} for label in result.labels
            ],
            "error": result.error,
            # `None` quando o adaptador nao rodou (UNAVAILABLE/FAILED) -
            # so existe avaliacao de relevancia clinica quando ha rotulos
            # para avaliar. "RELEVANT"/"NOT_RELEVANT"/"UNDETERMINED" (nunca
            # bool direto no JSON, para ficar explicito no laudo/auditoria).
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


def process_image_modality(db: Session, modality_state: AnalysisModalityState) -> None:
    media_asset = load_approved_media_asset(db, modality_state)
    storage = get_storage_adapter()
    content = storage.read_approved_object(media_asset.storage_key)

    dimensions = _parse_dimensions(media_asset.detected_mime_type, content)

    if dimensions is None:
        assessment_state = ModalityQualityState.INVALID
        metrics: dict = {"width": None, "height": None}
        factors = ["dimensoes_nao_determinadas"]
        summary = "Nao foi possivel ler as dimensoes da imagem a partir do arquivo."
    else:
        assessment = assess_image_quality(dimensions.width, dimensions.height)
        assessment_state = assessment.state
        metrics = assessment.metrics
        factors = assessment.factors
        summary = f"Imagem {dimensions.width}x{dimensions.height}."

    finding = record_finding(
        modality_state=modality_state,
        modality_type=ModalityType.IMAGE,
        quality_state=assessment_state,
        quality_metrics=metrics,
        quality_factors=factors,
        summary=summary,
    )
    db.add(finding)

    classification = classify_image_category(content)
    if classification is not None:
        roi = locate_region_of_interest(content)
        observation_metrics: dict = {
            "category": classification.category.value,
            "method": classification.method,
            "features": classification.features,
            "limitations": classification.limitations,
            "recommendation": classification.recommendation,
        }
        if roi is not None:
            observation_metrics["region_of_interest"] = {
                "quadrant": roi.quadrant,
                "bounding_box": roi.bounding_box,
                "edge_density_score": roi.edge_density_score,
            }
        observation = record_finding(
            modality_state=modality_state,
            modality_type=ModalityType.IMAGE,
            quality_state=assessment_state,
            quality_metrics=observation_metrics,
            quality_factors=[],
            summary=(
                f"Categoria candidata: {classification.category.value} "
                f"(metodo {classification.method})."
                + (f" Area de maior interesse: quadrante {roi.quadrant}." if roi else "")
            ),
            nature=FindingNature.MODEL_OBSERVATION,
        )
        db.add(observation)

    if assessment_state not in (ModalityQualityState.INSUFFICIENT, ModalityQualityState.INVALID):
        _run_image_recognition(
            db,
            modality_state,
            storage_key=media_asset.storage_key,
            content=content,
            quality_state=assessment_state,
        )
