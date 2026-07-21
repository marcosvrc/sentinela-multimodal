"""Regras de negocio de analise e upload de midia.

Fluxo implementado, cobrindo apenas ate a midia estar aprovada/rejeitada
(a fila, o orquestrador e o processamento por modalidade sao tratados em
outros modulos):

1. `create_analysis` - cria a analise em `CREATED`.
2. `request_upload_url` - valida metadados declarados, cria o `MediaAsset`
   em `AWAITING_UPLOAD`, pede ao storage adapter uma URL de upload para a
   AREA DE QUARENTENA e move a analise para `UPLOADING`.
3. O frontend envia o arquivo diretamente ao storage (S3 real; endpoint
   local no adaptador de dev) usando a URL recebida - o backend nao
   intermedia o arquivo.
4. `confirm_upload` - le o objeto na quarentena, confere tamanho/checksum
   reportado, deduz o tipo real pela assinatura do arquivo (nunca confia
   apenas no MIME declarado), roda o placeholder de varredura antimalware
   e, se tudo passar, promove o objeto para a area aprovada
   (`MediaUploadState.APPROVED`); caso contrario marca `REJECTED` e apaga
   o objeto da quarentena.

Cada etapa gera evento de auditoria (categoria FILES).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.core.enums import (
    AnalysisStatus,
    AuditCategory,
    AuditResult,
    MediaUploadState,
    ModalityType,
)
from app.core.errors import ApiError
from app.feature_flags.service import get_feature_flags
from app.media.models import Analysis, MediaAsset
from app.media.validation import (
    detect_mime_type_from_signature,
    run_placeholder_antimalware_scan,
    signature_matches_declared_mime,
    validate_declared_metadata,
)
from app.patients.models import Patient
from app.storage.base import ObjectMetadata, StorageAdapter

_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    sanitized = _FILENAME_SAFE_RE.sub("_", base).strip("._") or "arquivo"
    return sanitized[:150]


def _quarantine_key(institution_id: uuid.UUID, analysis_id: uuid.UUID, media_id: uuid.UUID) -> str:
    return f"{institution_id}/{analysis_id}/{media_id}"


def create_analysis(
    db: Session,
    institution_id: uuid.UUID,
    patient_id: uuid.UUID,
    actor: str,
    additional_text: str | None = None,
    structured_clinical_inputs: dict | None = None,
) -> Analysis:
    from app.patients.service import get_patient

    # Garante que o paciente existe e pertence a instituicao do requisitante
    # (mesmo padrao de app.observations.service.create_observation).
    get_patient(db, institution_id, patient_id)

    analysis = Analysis(
        institution_id=institution_id,
        patient_id=patient_id,
        status=AnalysisStatus.CREATED.value,
        additional_text=additional_text,
        structured_clinical_inputs=structured_clinical_inputs or {},
        created_by=actor,
    )
    db.add(analysis)
    db.flush()

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.ANALYSIS,
        action="ANALYSIS_CREATE",
        resource_type="analysis",
        resource_id=str(analysis.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        analysis_id=str(analysis.id),
    )
    db.commit()
    db.refresh(analysis)
    return analysis


def list_analyses(
    db: Session,
    institution_id: uuid.UUID,
    patient_id: uuid.UUID | None,
    page: int,
    page_size: int,
    *,
    created_by: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    patient_name: str | None = None,
    patient_medical_record_number: str | None = None,
) -> tuple[list[Analysis], int]:
    """Historico de analises exibido na tela `/analyses`, mais recentes primeiro.

    `created_by` filtra pelo `external_subject` exato do profissional que
    criou a analise (o mesmo valor gravado em `Analysis.created_by` - ver
    `create_analysis` acima); a resolucao para nome completo/opcoes de
    filtro cabe ao chamador (rota), que tem acesso a `identity.User`.
    `created_from`/`created_to` filtram por `created_at` (vigencia
    inclusiva em ambas as pontas).
    `patient_name`/`patient_medical_record_number` casam por substring
    (case-insensitive) no cadastro do paciente vinculado - mesmo padrao de
    `app.patients.service.list_patients` - e exigem um JOIN em `Patient`
    apenas quando informados (evita custo extra no caso comum).
    """
    filters = [Analysis.institution_id == institution_id]
    if patient_id is not None:
        filters.append(Analysis.patient_id == patient_id)
    if created_by:
        filters.append(Analysis.created_by == created_by)
    if created_from is not None:
        filters.append(Analysis.created_at >= created_from)
    if created_to is not None:
        filters.append(Analysis.created_at <= created_to)

    needs_patient_join = bool(patient_name or patient_medical_record_number)
    if patient_name:
        filters.append(Patient.full_name.ilike(f"%{patient_name.strip()}%"))
    if patient_medical_record_number:
        filters.append(
            Patient.medical_record_number.ilike(f"%{patient_medical_record_number.strip()}%")
        )

    count_stmt = select(func.count()).select_from(Analysis).where(*filters)
    items_stmt = select(Analysis).where(*filters)
    if needs_patient_join:
        count_stmt = count_stmt.join(Patient, Patient.id == Analysis.patient_id)
        items_stmt = items_stmt.join(Patient, Patient.id == Analysis.patient_id)

    total_items = db.scalar(count_stmt) or 0
    analyses = list(
        db.scalars(
            items_stmt.order_by(Analysis.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return analyses, total_items


def get_analysis(db: Session, institution_id: uuid.UUID, analysis_id: uuid.UUID) -> Analysis:
    analysis = db.scalar(
        select(Analysis).where(
            Analysis.id == analysis_id, Analysis.institution_id == institution_id
        )
    )
    if analysis is None:
        raise ApiError(
            code="ANALYSIS_NOT_FOUND", message="Analise nao encontrada.", status_code=404
        )
    return analysis


def _get_media_asset(
    db: Session, institution_id: uuid.UUID, analysis_id: uuid.UUID, media_id: uuid.UUID
) -> MediaAsset:
    media_asset = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == media_id,
            MediaAsset.analysis_id == analysis_id,
            MediaAsset.institution_id == institution_id,
        )
    )
    if media_asset is None:
        raise ApiError(
            code="MEDIA_ASSET_NOT_FOUND", message="Midia nao encontrada.", status_code=404
        )
    return media_asset


_MODALITY_FLAG_ATTR: dict[ModalityType, str] = {
    ModalityType.AUDIO: "modality_audio_enabled",
    ModalityType.VIDEO: "modality_video_enabled",
    ModalityType.IMAGE: "modality_image_enabled",
}


def _is_modality_enabled(db: Session, modality_type: ModalityType) -> bool:
    """TEXT nunca e afetado (nao usa upload de midia, ver `app.media.
    validation.UPLOADABLE_MODALITIES`) - qualquer modalidade fora do mapa
    e considerada habilitada por padrao, nunca bloqueada por omissao."""
    attr = _MODALITY_FLAG_ATTR.get(modality_type)
    if attr is None:
        return True
    flags = get_feature_flags(db)
    return bool(getattr(flags, attr))


def request_upload_url(
    db: Session,
    storage: StorageAdapter,
    institution_id: uuid.UUID,
    analysis_id: uuid.UUID,
    actor: str,
    modality_type: ModalityType,
    filename: str,
    mime_type: str,
    size_bytes: int,
) -> tuple[MediaAsset, object]:
    analysis = get_analysis(db, institution_id, analysis_id)

    if analysis.status not in (AnalysisStatus.CREATED.value, AnalysisStatus.UPLOADING.value):
        raise ApiError(
            code="ANALYSIS_NOT_ACCEPTING_UPLOADS",
            message=f"Analise em estado '{analysis.status}' nao aceita novas midias.",
            status_code=409,
        )

    if not _is_modality_enabled(db, modality_type):
        raise ApiError(
            code="MODALITY_DISABLED",
            message=(
                f"A modalidade {modality_type.value} esta desligada na tela de "
                "feature flags (/admin/feature-flags) - novas midias deste tipo nao "
                "sao aceitas ate que um administrador a reative."
            ),
            status_code=422,
        )

    field_errors = validate_declared_metadata(modality_type, mime_type, size_bytes)
    if field_errors:
        raise ApiError(
            code="VALIDATION_ERROR",
            message="Metadados de midia invalidos.",
            status_code=422,
            field_errors=field_errors,
        )

    media_asset = MediaAsset(
        institution_id=institution_id,
        analysis_id=analysis_id,
        modality_type=modality_type.value,
        upload_state=MediaUploadState.AWAITING_UPLOAD.value,
        storage_key="",  # preenchido abaixo, depois que o id existe
        original_filename=_sanitize_filename(filename),
        declared_mime_type=mime_type,
        declared_size_bytes=size_bytes,
        created_by=actor,
    )
    db.add(media_asset)
    db.flush()

    quarantine_key = _quarantine_key(institution_id, analysis_id, media_asset.id)
    media_asset.storage_key = quarantine_key

    presigned = storage.create_presigned_upload(
        quarantine_key=quarantine_key,
        declared_mime_type=mime_type,
        declared_size_bytes=size_bytes,
    )

    if analysis.status == AnalysisStatus.CREATED.value:
        analysis.status = AnalysisStatus.UPLOADING.value

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.FILES,
        action="MEDIA_UPLOAD_URL_ISSUED",
        resource_type="media_asset",
        resource_id=str(media_asset.id),
        result=AuditResult.SUCCESS,
        institution_id=institution_id,
        analysis_id=str(analysis_id),
        event_metadata={"modality_type": modality_type.value, "declared_mime_type": mime_type},
    )
    db.commit()
    db.refresh(media_asset)
    return media_asset, presigned


def confirm_upload(
    db: Session,
    storage: StorageAdapter,
    institution_id: uuid.UUID,
    analysis_id: uuid.UUID,
    media_id: uuid.UUID,
    actor: str,
    reported_checksum_sha256: str,
) -> MediaAsset:
    media_asset = _get_media_asset(db, institution_id, analysis_id, media_id)

    if media_asset.upload_state != MediaUploadState.AWAITING_UPLOAD.value:
        raise ApiError(
            code="MEDIA_ASSET_ALREADY_CONFIRMED",
            message=f"Midia ja esta em estado '{media_asset.upload_state}'.",
            status_code=409,
        )

    metadata = storage.stat_quarantined_object(media_asset.storage_key)
    if metadata is None:
        raise ApiError(
            code="MEDIA_NOT_UPLOADED",
            message="Nenhum objeto encontrado na quarentena para esta midia.",
            status_code=409,
        )

    media_asset.actual_size_bytes = metadata.size_bytes
    media_asset.checksum_sha256 = metadata.checksum_sha256

    rejection_reason = _evaluate_uploaded_object(media_asset, metadata, reported_checksum_sha256)

    if rejection_reason is not None:
        media_asset.upload_state = MediaUploadState.REJECTED.value
        media_asset.rejection_reason = rejection_reason
        storage.delete_quarantined_object(media_asset.storage_key)
        audit_result = AuditResult.DENIED
        audit_action = "MEDIA_UPLOAD_REJECTED"
    else:
        approved_key = media_asset.storage_key
        storage.promote(quarantine_key=media_asset.storage_key, approved_key=approved_key)
        media_asset.upload_state = MediaUploadState.APPROVED.value
        audit_result = AuditResult.SUCCESS
        audit_action = "MEDIA_UPLOAD_APPROVED"

    media_asset.confirmed_at = datetime.now(tz=timezone.utc)

    audit_service.record_event(
        db,
        actor=actor,
        category=AuditCategory.FILES,
        action=audit_action,
        resource_type="media_asset",
        resource_id=str(media_asset.id),
        result=audit_result,
        institution_id=institution_id,
        analysis_id=str(analysis_id),
        justification=rejection_reason,
        event_metadata={
            "modality_type": media_asset.modality_type,
            "detected_mime_type": media_asset.detected_mime_type,
        },
    )
    db.commit()
    db.refresh(media_asset)
    return media_asset


def _evaluate_uploaded_object(
    media_asset: MediaAsset, metadata: ObjectMetadata, reported_checksum: str
) -> str | None:
    """Retorna o motivo de rejeicao, ou `None` se o objeto deve ser aprovado."""
    if not reported_checksum or reported_checksum.lower() != metadata.checksum_sha256.lower():
        return "Checksum reportado nao confere com o checksum calculado do objeto."

    if metadata.size_bytes != media_asset.declared_size_bytes:
        return (
            f"Tamanho real ({metadata.size_bytes} bytes) difere do declarado "
            f"({media_asset.declared_size_bytes} bytes)."
        )

    detected_mime = detect_mime_type_from_signature(metadata.content_prefix)
    media_asset.detected_mime_type = detected_mime
    if not signature_matches_declared_mime(detected_mime, media_asset.declared_mime_type):
        return "Assinatura do arquivo nao corresponde ao MIME declarado."

    scan_result = run_placeholder_antimalware_scan(metadata.content_prefix)
    if not scan_result.clean:
        return f"Reprovado na varredura antimalware: {scan_result.reason}"

    return None


def list_media_assets(
    db: Session, institution_id: uuid.UUID, analysis_id: uuid.UUID
) -> list[MediaAsset]:
    get_analysis(db, institution_id, analysis_id)
    return list(
        db.scalars(
            select(MediaAsset)
            .where(
                MediaAsset.analysis_id == analysis_id,
                MediaAsset.institution_id == institution_id,
            )
            .order_by(MediaAsset.created_at)
        ).all()
    )
