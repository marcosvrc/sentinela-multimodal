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

import base64
import logging

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

_logger = logging.getLogger(__name__)


def _parse_dimensions(detected_mime_type: str | None, content: bytes) -> ImageDimensions | None:
    if detected_mime_type == "application/dicom":
        return _parse_dicom_dimensions(content)
    if detected_mime_type == "image/png":
        return parse_png_dimensions(content)
    if detected_mime_type == "image/jpeg":
        return parse_jpeg_dimensions(content)
    return parse_png_dimensions(content) or parse_jpeg_dimensions(content)


def _parse_dicom_dimensions(content: bytes) -> ImageDimensions | None:
    """Extrai dimensões de um arquivo DICOM via pydicom."""
    try:
        import io

        import pydicom
        ds = pydicom.dcmread(io.BytesIO(content), force=True)
        rows = getattr(ds, "Rows", None)
        cols = getattr(ds, "Columns", None)
        if rows and cols:
            return ImageDimensions(width=int(cols), height=int(rows))
        return None
    except Exception:  # noqa: BLE001
        return None


def _extract_dicom_metadata(content: bytes) -> dict | None:
    """Extrai metadados clínicos de um arquivo DICOM."""
    try:
        import io

        import pydicom
        ds = pydicom.dcmread(io.BytesIO(content), force=True)
        return {
            "study_instance_uid": str(getattr(ds, "StudyInstanceUID", "")),
            "series_instance_uid": str(getattr(ds, "SeriesInstanceUID", "")),
            "sop_instance_uid": str(getattr(ds, "SOPInstanceUID", "")),
            "modality": str(getattr(ds, "Modality", "")),
            "body_part": str(getattr(ds, "BodyPartExamined", "")),
            "patient_name": str(getattr(ds, "PatientName", "")),
            "institution_name": str(getattr(ds, "InstitutionName", "")),
            "manufacturer": str(getattr(ds, "Manufacturer", "")),
            "study_description": str(getattr(ds, "StudyDescription", "")),
            "series_description": str(getattr(ds, "SeriesDescription", "")),
        }
    except Exception:  # noqa: BLE001
        return None


def _convert_dicom_to_png(content: bytes) -> bytes | None:
    """Converte pixel data DICOM para PNG via pydicom + Pillow."""
    try:
        import io

        import numpy as np
        import pydicom
        from PIL import Image

        ds = pydicom.dcmread(io.BytesIO(content), force=True)
        pixel_array = ds.pixel_array

        # Normaliza para 8-bit
        if pixel_array.dtype != np.uint8:
            arr = pixel_array.astype(float)
            arr = ((arr - arr.min()) / (arr.max() - arr.min() + 1e-9) * 255).astype(np.uint8)
        else:
            arr = pixel_array

        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None


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

    is_dicom = media_asset.detected_mime_type == "application/dicom"
    dimensions = _parse_dimensions(media_asset.detected_mime_type, content)

    # Se DICOM, extrai metadados e faz upload ao Azure DICOM Service
    dicom_metadata: dict | None = None
    gpt_content = content  # bytes para GPT-4 Vision
    if is_dicom:
        dicom_metadata = _extract_dicom_metadata(content)
        # Upload ao Azure DICOM Service (se configurado)
        from app.integrations.dicom import get_dicom_client
        dicom_client = get_dicom_client()
        if dicom_client:
            dicom_client.store(content)
        # Converte para PNG para análise visual (GPT-4 Vision)
        png_bytes = _convert_dicom_to_png(content)
        if png_bytes:
            gpt_content = png_bytes

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

    # Achado de metadados DICOM (quando é DICOM)
    if is_dicom and dicom_metadata:
        modality_str = dicom_metadata.get("modality") or "desconhecida"
        body_part = dicom_metadata.get("body_part") or "não especificada"
        institution = dicom_metadata.get("institution_name") or "não informada"
        study_desc = dicom_metadata.get("study_description") or ""
        dicom_finding = record_finding(
            modality_state=modality_state,
            modality_type=ModalityType.IMAGE,
            quality_state=assessment_state,
            quality_metrics={
                "format": "DICOM",
                **{k: v for k, v in dicom_metadata.items() if v},
            },
            quality_factors=[],
            summary=(
                f"Imagem médica DICOM — Modalidade: {modality_str}, "
                f"Parte do corpo: {body_part}, "
                f"Instituição: {institution}"
                + (f", Estudo: {study_desc}" if study_desc else "")
            ),
            nature=FindingNature.MODEL_OBSERVATION,
        )
        db.add(dicom_finding)

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
        # Azure AI Vision (rótulos genéricos) — só roda quando a feature
        # flag `image_recognition_enabled` está ligada. Desligada por
        # padrão porque os resultados são genéricos demais para contexto
        # clínico (ex.: "pessoa", "roupas", "parede").
        from app.feature_flags.service import get_feature_flags
        flags = get_feature_flags(db)
        if flags.image_recognition_enabled:
            _run_image_recognition(
                db,
                modality_state,
                storage_key=media_asset.storage_key,
                content=content,
                quality_state=assessment_state,
            )

        # GPT-4 Vision (análise contextual clínica) — roda sempre que
        # houver OPENAI_API_KEY configurada, independente da flag acima.
        # Interpreta contexto de saúde (dor, postura, expressão facial)
        # que o Azure Vision não consegue detectar.
        _run_vision_gpt(
            db,
            modality_state,
            content=gpt_content,
            detected_mime="image/png" if is_dicom else (media_asset.detected_mime_type or "image/jpeg"),
            quality_state=assessment_state,
        )


def _run_vision_gpt(
    db: Session,
    modality_state: AnalysisModalityState,
    *,
    content: bytes,
    detected_mime: str,
    quality_state: ModalityQualityState,
) -> None:
    """Análise contextual da imagem via GPT-4o (visão multimodal).

    Diferente do Azure AI Vision (rótulos genéricos de objetos), o GPT-4o
    interpreta o CONTEXTO CLÍNICO da imagem: expressão facial de dor,
    postura, sinais visíveis de desconforto, equipamentos médicos, lesões,
    etc. O resultado é um achado MODEL_OBSERVATION com relevância clínica
    confirmada quando o modelo identifica contexto de saúde.
    """
    try:
        from openai import OpenAI

        from app.core.config import get_settings

        settings = get_settings()
        if not settings.openai_api_key:
            return

        client = OpenAI(api_key=settings.openai_api_key)
        model = settings.openai_model or "gpt-4o-mini"

        # Codifica imagem em base64 para enviar via API
        mime = detected_mime if detected_mime in ("image/jpeg", "image/png") else "image/jpeg"
        b64_image = base64.b64encode(content).decode("utf-8")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Voce e um assistente de apoio clinico. Analise a imagem e descreva "
                        "objetivamente o que voce observa com relevancia clinica: expressao "
                        "facial (dor, desconforto), postura corporal, sinais visiveis de "
                        "sofrimento, lesoes, equipamentos medicos, ou qualquer outro elemento "
                        "que um profissional de saude consideraria relevante. Se a imagem NAO "
                        "tiver conteudo clinico (paisagem, comida, objeto generico), diga "
                        "explicitamente que nao ha contexto clinico identificado. Responda "
                        "sempre em portugues, de forma objetiva e concisa (max 3 frases)."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64_image}",
                                "detail": "low",
                            },
                        },
                        {
                            "type": "text",
                            "text": "Descreva o conteudo clinico desta imagem.",
                        },
                    ],
                },
            ],
            max_tokens=300,
            store=False,
        )

        description = response.choices[0].message.content or ""
        if not description.strip():
            return

        # Determina relevância: se GPT diz "não há contexto clínico", marca NOT_RELEVANT
        is_not_relevant = any(
            phrase in description.lower()
            for phrase in [
                "não há contexto clínico",
                "nao ha contexto clinico",
                "não possui relevância clínica",
                "sem contexto clínico",
                "sem relevância clínica",
            ]
        )
        clinical_rel = "NOT_RELEVANT" if is_not_relevant else "RELEVANT"

        finding = record_finding(
            modality_state=modality_state,
            modality_type=ModalityType.IMAGE,
            quality_state=quality_state,
            quality_metrics={
                "provider": "openai",
                "model": model,
                "analysis_type": "vision_contextual",
                "clinical_relevance": clinical_rel,
            },
            quality_factors=[],
            summary=f"Análise contextual (GPT-4 Vision): {description.strip()}",
            nature=FindingNature.MODEL_OBSERVATION,
        )
        db.add(finding)

    except Exception as exc:  # noqa: BLE001
        _logger.warning("GPT-4 Vision analysis failed: %s", exc)
